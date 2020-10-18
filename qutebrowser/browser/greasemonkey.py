# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Load, parse and make available Greasemonkey scripts."""

import re
import os
import json
import fnmatch
import functools
import glob
import textwrap
import typing
import enum

import attr
from PyQt5.QtCore import pyqtSignal, QObject, QUrl

from qutebrowser.utils import (log, standarddir, jinja, objreg, utils,
                               javascript, urlmatch, version, usertypes,
                               qtutils, message)
from qutebrowser.api import cmdutils
from qutebrowser.browser import downloads
from qutebrowser.misc import objects
if typing.TYPE_CHECKING:
    from qutebrowser.browser.qtnetworkdownloads import DownloadItem


gm_manager = typing.cast('GreasemonkeyManager', None)


def _scripts_dir():
    """Get the directory of the scripts."""
    return os.path.join(standarddir.data(), 'greasemonkey')


@attr.s
class _Resource:

    """A resource for a greasemonkey userscript."""

    name = attr.ib()
    url = attr.ib()


class GreasemonkeyScript:

    """Container class for userscripts, parses metadata blocks."""

    def __init__(self, properties, code,  # noqa: C901 pragma: no mccabe
                 filename=None):
        self._code = code
        self.includes = []  # type: typing.Sequence[str]
        self.matches = []  # type: typing.Sequence[str]
        self.excludes = []  # type: typing.Sequence[str]
        self.requires = []  # type: typing.Sequence[str]
        self.resources = []  # type: typing.Sequence[_Resource]
        self.resource_text = {}  # type: typing.Dict[str, str]
        self.description = None
        self.namespace = None
        self.run_at = None
        self.script_meta = None
        self.runs_on_sub_frames = True
        self.jsworld = "main"
        self.name = ''

        for name, value in properties:
            if name == 'name':
                self.name = value
            elif name == 'namespace':
                self.namespace = value
            elif name == 'description':
                self.description = value
            elif name == 'include':
                self.includes.append(value)
            elif name == 'match':
                self.matches.append(value)
            elif name in ['exclude', 'exclude_match']:
                self.excludes.append(value)
            elif name == 'run-at':
                self.run_at = value
            elif name == 'noframes':
                self.runs_on_sub_frames = False
            elif name == 'require':
                self.requires.append(value)
            elif name == 'resource':
                resource_name, url = value.split(maxsplit=1)
                self.resources.append(_Resource(resource_name, url))
            elif name == 'qute-js-world':
                self.jsworld = value

        if not self.name:
            if filename:
                self.name = filename
            else:
                raise ValueError(
                    "@name key required or pass filename to init."
                )

    HEADER_REGEX = r'// ==UserScript==|\n+// ==/UserScript==\n'
    PROPS_REGEX = r'// @(?P<prop>[^\s]+)\s*(?P<val>.*)'

    @classmethod
    def parse(cls, source, filename=None) -> "GreasemonkeyScript":
        """GreasemonkeyScript factory.

        Takes a userscript source and returns a GreasemonkeyScript.
        Parses the Greasemonkey metadata block, if present, to fill out
        attributes.
        """
        matches = re.split(cls.HEADER_REGEX, source, maxsplit=2)
        try:
            _head, props, _code = matches
        except ValueError:
            props = ""
        script = cls(
            re.findall(cls.PROPS_REGEX, props),
            source,
            filename=filename
        )
        script.script_meta = props
        if not script.includes and not script.matches:
            script.includes = ['*']
        return script

    def needs_document_end_workaround(self):
        """Check whether to force @run-at document-end.

        This needs to be done on QtWebEngine with Qt 5.12 for known-broken
        scripts.

        On Qt 5.12, accessing the DOM isn't possible with "@run-at
        document-start". It was documented to be impossible before, but seems
        to work fine.

        However, some scripts do DOM access with "@run-at document-start". Fix
        those by forcing them to use document-end instead.
        """
        if objects.backend != usertypes.Backend.QtWebEngine:
            assert objects.backend == usertypes.Backend.QtWebKit, objects.backend
            return False
        elif not qtutils.version_check('5.12', compiled=False):
            return False

        broken_scripts = [
            ('http://userstyles.org', None),
            ('https://github.com/ParticleCore', 'Iridium'),
        ]
        return any(self._matches_id(namespace=namespace, name=name)
                   for namespace, name in broken_scripts)

    def _matches_id(self, *, namespace, name):
        """Check if this script matches the given namespace/name.

        Both namespace and name can be None in order to match any script.
        """
        matches_namespace = namespace is None or self.namespace == namespace
        matches_name = name is None or self.name == name
        return matches_namespace and matches_name

    def code(self):
        """Return the processed JavaScript code of this script.

        Adorns the source code with GM_* methods for Greasemonkey
        compatibility and wraps it in an IIFE to hide it within a
        lexical scope. Note that this means line numbers in your
        browser's debugger/inspector will not match up to the line
        numbers in the source script directly.
        """
        # Don't use Proxy on this webkit version, the support isn't there.
        use_proxy = not (
            objects.backend == usertypes.Backend.QtWebKit and
            version.qWebKitVersion() == '602.1')
        template = jinja.js_environment.get_template('greasemonkey_wrapper.js')
        return template.render(
            scriptName=javascript.string_escape(
                "/".join([self.namespace or '', self.name])),
            scriptInfo=self._meta_json(),
            scriptMeta=javascript.string_escape(self.script_meta or ''),
            scriptSource=self._code,
            resourceText=json.dumps(self.resource_text),
            use_proxy=use_proxy)

    def _meta_json(self):
        return json.dumps({
            'name': self.name,
            'description': self.description,
            'matches': self.matches,
            'includes': self.includes,
            'excludes': self.excludes,
            'resources': {
                resource.name: {
                    'name': resource.name,
                    'mimetype': '',  # currently unsupported
                    'url': resource.url,
                }
                for resource in self.resources},
            'run-at': self.run_at,
        })

    def add_required_script(self, source):
        """Add the source of a required script to this script."""
        # The additional source is indented in case it also contains a
        # metadata block. Because we pass everything at once to
        # QWebEngineScript and that would parse the first metadata block
        # found as the valid one.
        self._code = "\n".join([textwrap.indent(source, "    "), self._code])

    def add_resource(self, resource_name: str, resource_text: str):
        """Add the text of a required resource to this script."""
        if resource_name in self.resource_text:
            log.greasemonkey.debug("Duplicate resource: " + resource_name)
            # TODO message.error ?
        self.resource_text[resource_name] = resource_text


@attr.s
class MatchingScripts:

    """All userscripts registered to run on a particular url."""

    url = attr.ib()
    start = attr.ib(default=attr.Factory(list))
    end = attr.ib(default=attr.Factory(list))
    idle = attr.ib(default=attr.Factory(list))


class GreasemonkeyMatcher:

    """Check whether scripts should be loaded for a given URL."""

    # https://wiki.greasespot.net/Include_and_exclude_rules#Greaseable_schemes
    # Limit the schemes scripts can run on due to unreasonable levels of
    # exploitability
    GREASEABLE_SCHEMES = ['http', 'https', 'ftp', 'file']

    def __init__(self, url):
        self._url = url
        self._url_string = url.toString(QUrl.FullyEncoded)
        self.is_greaseable = url.scheme() in self.GREASEABLE_SCHEMES

    def _match_pattern(self, pattern):
        # For include and exclude rules if they start and end with '/' they
        # should be treated as a (ecma syntax) regular expression.
        if pattern.startswith('/') and pattern.endswith('/'):
            matches = re.search(pattern[1:-1], self._url_string, flags=re.I)
            return matches is not None

        # Otherwise they are glob expressions.
        return fnmatch.fnmatch(self._url_string, pattern)

    def matches(self, script):
        """Check whether the URL matches filtering rules of the script."""
        assert self.is_greaseable
        matching_includes = any(self._match_pattern(pat)
                                for pat in script.includes)
        matching_match = any(urlmatch.UrlPattern(pat).matches(self._url)
                             for pat in script.matches)
        matching_excludes = any(self._match_pattern(pat)
                                for pat in script.excludes)
        return (matching_includes or matching_match) and not matching_excludes


class _RequirementType(enum.Enum):
    requires = 1
    resources = 2


_FOLDER_NAME_OF_REQUIREMENT = {
    _RequirementType.requires: 'requires',
    _RequirementType.resources: 'resources',
}


class GreasemonkeyManager(QObject):

    """Manager of userscripts and a Greasemonkey compatible environment.

    Signals:
        scripts_reloaded: Emitted when scripts are reloaded from disk.
            Any cached or already-injected scripts should be
            considered obsolete.
    """

    scripts_reloaded = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run_start = []  # type: typing.List[GreasemonkeyScript]
        self._run_end = []  # type: typing.List[GreasemonkeyScript]
        self._run_idle = []  # type: typing.List[GreasemonkeyScript]
        self._in_progress_dls = [
        ]  # type: typing.List[downloads.AbstractDownloadItem]

        self.load_scripts()

    def load_scripts(self, *, force: bool = False):
        """Re-read Greasemonkey scripts from disk.

        The scripts are read from a 'greasemonkey' subdirectory in
        qutebrowser's data directory (see `:version`).

        Args:
            force: For any scripts that have required dependencies,
                   re-download them.
        """
        self._run_start = []
        self._run_end = []
        self._run_idle = []

        scripts_dir = os.path.abspath(_scripts_dir())
        log.greasemonkey.debug("Reading scripts from: {}".format(scripts_dir))
        for script_filename in glob.glob(os.path.join(scripts_dir, '*.js')):
            if not os.path.isfile(script_filename):
                continue
            script_path = os.path.join(scripts_dir, script_filename)
            with open(script_path, encoding='utf-8-sig') as script_file:
                script = GreasemonkeyScript.parse(script_file.read(),
                                                  script_filename)
                if not script.name:
                    script.name = script_filename
                self.add_script(script, force)
        self.scripts_reloaded.emit()

    def add_script(self, script: GreasemonkeyScript, force: bool = False):
        """Add a GreasemonkeyScript to this manager.

        Args:
            force: Fetch and overwrite any dependancies which are
                   already locally cached.
        """
        if script.requires or script.resources:
            log.greasemonkey.debug(
                "Deferring script until requirements are "
                "fulfilled: {}".format(script.name))
            self._get_requirements(script, force)
        else:
            self._add_script(script)

    def _add_script(self, script: GreasemonkeyScript):
        if script.run_at == 'document-start':
            self._run_start.append(script)
        elif script.run_at == 'document-end':
            self._run_end.append(script)
        elif script.run_at == 'document-idle':
            self._run_idle.append(script)
        else:
            if script.run_at:
                log.greasemonkey.warning("Script {} has invalid run-at "
                                         "defined, defaulting to "
                                         "document-end"
                                         .format(script.name))
                # Default as per
                # https://wiki.greasespot.net/Metadata_Block#.40run-at
            self._run_end.append(script)
        log.greasemonkey.debug("Loaded script: {}".format(script.name))

    def _required_url_to_file_path(self, requirement_type: _RequirementType,
                                   url: str):
        requires_dir = os.path.join(
            _scripts_dir(), _FOLDER_NAME_OF_REQUIREMENT[requirement_type])
        if not os.path.exists(requires_dir):
            os.mkdir(requires_dir)
        return os.path.join(requires_dir, utils.sanitize_filename(url))

    def _on_required_download_finished(self, script: GreasemonkeyScript,
                                       download: 'DownloadItem'):
        self._in_progress_dls.remove(download)
        if not self._add_script_with_requires(script):
            log.greasemonkey.debug(
                "Finished download {} for script {} "
                "but some requirements are still pending"
                .format(download.basename, script.name))

    def _add_script_with_requires(self, script: GreasemonkeyScript,
                                  quiet: bool = False):
        """Add a script with pending downloads to this GreasemonkeyManager.

        Specifically a script that has dependancies specified via an
        `@require` or `@resource` rule.

        Args:
            script: The GreasemonkeyScript to add.
            quiet: True to suppress the scripts_reloaded signal after
                   adding `script`.
        Returns: True if the script was added, False if there are still
                 dependancies being downloaded.
        """
        # See if we are still waiting on any required scripts for this one
        if {download.requested_url for download in self._in_progress_dls} & (
            set(script.requires) | {
                resource.url for resource in script.resources}):
            return False

        # Need to add the required scripts to the IIFE now
        for url in reversed(script.requires):
            target_path = self._required_url_to_file_path(
                _RequirementType.requires, url)
            log.greasemonkey.debug(
                "Adding required script for {} to IIFE: {}"
                .format(script.name, url))
            with open(target_path, encoding='utf8') as f:
                script.add_required_script(f.read())

        for resource in script.resources:
            target_path = self._required_url_to_file_path(
                _RequirementType.resources, resource.url)
            log.greasemonkey.debug(
                "Adding required resource for {} to IIFE: {}"
                .format(script.name, resource.url))
            with open(target_path, encoding='utf8') as f:
                script.add_resource(resource.name, f.read())

        self._add_script(script)
        if not quiet:
            self.scripts_reloaded.emit()
        return True

    def _get_requirements(self, script: GreasemonkeyScript, force: bool = False
                          ) -> None:
        all_downloads = [
            (url, self._required_url_to_file_path(
                _RequirementType.requires, url)) for url in script.requires
        ]+[
            (resource.url, self._required_url_to_file_path(
                _RequirementType.resources, resource.url))
            for resource in script.resources]

        required_dls = []  # type: typing.List[typing.Tuple[str, QUrl, str]]
        for url, path in all_downloads:
            url_ = QUrl(url)
            file_exists = os.path.exists(path)

            if url_.isRelative():
                if not file_exists:
                    message.error("Missing relative resource: {} for script {}"
                                  .format(url, script.name))
                    return

                log.greasemonkey.debug(
                    "Resource URL is relative: " + url + ". "
                    "Force refresh is not supported.")
                continue

            if force or not file_exists:
                required_dls.append((url, url_, path))

        if not required_dls:
            # All the required files exist already
            self._add_script_with_requires(script, quiet=True)
            return

        download_manager = objreg.get('qtnetwork-download-manager')

        for url, url_, target_path in required_dls:
            target = downloads.FileDownloadTarget(target_path,
                                                  force_overwrite=True)
            download = download_manager.get(url_, target=target,
                                            auto_remove=True)
            download.requested_url = url
            self._in_progress_dls.append(download)
            if download.successful:
                self._on_required_download_finished(script, download)
            else:
                download.finished.connect(
                    functools.partial(self._on_required_download_finished,
                                      script, download))

    def scripts_for(self, url):
        """Fetch scripts that are registered to run for url.

        returns a tuple of lists of scripts meant to run at (document-start,
        document-end, document-idle)
        """
        matcher = GreasemonkeyMatcher(url)
        if not matcher.is_greaseable:
            return MatchingScripts(url, [], [], [])
        return MatchingScripts(
            url=url,
            start=[script for script in self._run_start
                   if matcher.matches(script)],
            end=[script for script in self._run_end
                 if matcher.matches(script)],
            idle=[script for script in self._run_idle
                  if matcher.matches(script)]
        )

    def all_scripts(self):
        """Return all scripts found in the configured script directory."""
        return self._run_start + self._run_end + self._run_idle


@cmdutils.register()
def greasemonkey_reload(force=False):
    """Re-read Greasemonkey scripts from disk.

    The scripts are read from a 'greasemonkey' subdirectory in
    qutebrowser's data directory (see `:version`).

    Args:
        force: For any scripts that have required dependencies,
                re-download them.
    """
    gm_manager.load_scripts(force=force)


def init():
    """Initialize Greasemonkey support."""
    global gm_manager
    gm_manager = GreasemonkeyManager()

    try:
        os.mkdir(_scripts_dir())
    except FileExistsError:
        pass
