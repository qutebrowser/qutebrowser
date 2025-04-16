# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Various utilities used inside tests."""

import io
import re
import enum
import gzip
import pprint
import platform
import os.path
import contextlib
import pathlib
import subprocess
import importlib.util
import importlib.machinery
from typing import Optional

import pytest

from qutebrowser.qt.gui import QColor

from qutebrowser.utils import log, utils, version

ON_CI = 'CI' in os.environ


class Color(QColor):

    """A QColor with a nicer repr()."""

    def __repr__(self):
        return utils.get_repr(self, constructor=True, red=self.red(),
                              green=self.green(), blue=self.blue(),
                              alpha=self.alpha())


class PartialCompareOutcome:

    """Storage for a partial_compare error.

    Evaluates to False if an error was found.

    Attributes:
        error: A string describing an error or None.
    """

    def __init__(self, error=None):
        self.error = error

    def __bool__(self):
        return self.error is None

    def __repr__(self):
        return 'PartialCompareOutcome(error={!r})'.format(self.error)

    def __str__(self):
        return 'true' if self.error is None else 'false'


def print_i(text, indent, error=False):
    if error:
        text = '| ****** {} ******'.format(text)
    for line in text.splitlines():
        print('|   ' * indent + line)


def _partial_compare_dict(val1, val2, *, indent):
    for key in val2:
        if key not in val1:
            outcome = PartialCompareOutcome(
                "Key {!r} is in second dict but not in first!".format(key))
            print_i(outcome.error, indent, error=True)
            return outcome
        outcome = partial_compare(val1[key], val2[key], indent=indent + 1)
        if not outcome:
            return outcome
    return PartialCompareOutcome()


def _partial_compare_list(val1, val2, *, indent):
    if len(val1) < len(val2):
        outcome = PartialCompareOutcome(
            "Second list is longer than first list")
        print_i(outcome.error, indent, error=True)
        return outcome
    for item1, item2 in zip(val1, val2):
        outcome = partial_compare(item1, item2, indent=indent + 1)
        if not outcome:
            return outcome
    return PartialCompareOutcome()


def _partial_compare_float(val1, val2, *, indent):
    if val1 == pytest.approx(val2):
        return PartialCompareOutcome()

    return PartialCompareOutcome("{!r} != {!r} (float comparison)".format(
        val1, val2))


def _partial_compare_str(val1, val2, *, indent):
    if pattern_match(pattern=val2, value=val1):
        return PartialCompareOutcome()

    return PartialCompareOutcome("{!r} != {!r} (pattern matching)".format(
        val1, val2))


def _partial_compare_eq(val1, val2, *, indent):
    if val1 == val2:
        return PartialCompareOutcome()
    return PartialCompareOutcome("{!r} != {!r}".format(val1, val2))


def gha_group_begin(name):
    """Get a string to begin a GitHub Actions group.

    Should only be called on CI.
    """
    assert ON_CI
    return '::group::' + name


def gha_group_end():
    """Get a string to end a GitHub Actions group.

    Should only be called on CI.
    """
    assert ON_CI
    return '::endgroup::'


def partial_compare(val1, val2, *, indent=0):
    """Do a partial comparison between the given values.

    For dicts, keys in val2 are checked, others are ignored.
    For lists, entries at the positions in val2 are checked, others ignored.
    For other values, == is used.

    This happens recursively.
    """
    if ON_CI and indent == 0:
        print(gha_group_begin('Comparison'))

    print_i("Comparing", indent)
    print_i(pprint.pformat(val1), indent + 1)
    print_i("|---- to ----", indent)
    print_i(pprint.pformat(val2), indent + 1)

    if val2 is Ellipsis:
        print_i("Ignoring ellipsis comparison", indent, error=True)
        return PartialCompareOutcome()
    elif type(val1) is not type(val2):
        outcome = PartialCompareOutcome(
            "Different types ({}, {}) -> False".format(type(val1).__name__,
                                                       type(val2).__name__))
        print_i(outcome.error, indent, error=True)
        return outcome

    handlers = {
        dict: _partial_compare_dict,
        list: _partial_compare_list,
        float: _partial_compare_float,
        str: _partial_compare_str,
    }

    for typ, handler in handlers.items():
        if isinstance(val2, typ):
            print_i("|======= Comparing as {}".format(typ.__name__), indent)
            outcome = handler(val1, val2, indent=indent)
            break
    else:
        print_i("|======= Comparing via ==", indent)
        outcome = _partial_compare_eq(val1, val2, indent=indent)
    print_i("---> {}".format(outcome), indent)

    if ON_CI and indent == 0:
        print(gha_group_end())

    return outcome


def pattern_match(*, pattern, value):
    """Do fnmatch.fnmatchcase like matching, but only with * active.

    Return:
        True on a match, False otherwise.
    """
    re_pattern = '.*'.join(re.escape(part) for part in pattern.split('*'))
    return re.fullmatch(re_pattern, value, flags=re.DOTALL) is not None


def abs_datapath():
    """Get the absolute path to the end2end data directory."""
    path = pathlib.Path(__file__).parent / '..' / 'end2end' / 'data'
    return path.resolve()


def substitute_testdata(path):
    r"""Replace the (testdata) placeholder in path with `abs_datapath()`.

    If path is starting with file://, return path as an URI with file:// removed. This
    is useful if path is going to be inserted into an URI:

    >>> path = substitute_testdata("C:\Users\qute")
    >>> f"file://{path}/slug  # results in valid URI
    'file:///C:/Users/qute/slug'
    """
    if path.startswith('file://'):
        testdata_path = abs_datapath().as_uri().replace('file://', '')
    else:
        testdata_path = str(abs_datapath())

    return path.replace('(testdata)', testdata_path)


@contextlib.contextmanager
def nop_contextmanager():
    yield


@contextlib.contextmanager
def change_cwd(path):
    """Use a path as current working directory."""
    old_cwd = pathlib.Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


@contextlib.contextmanager
def ignore_bs4_warning():
    """WORKAROUND for https://bugs.launchpad.net/beautifulsoup/+bug/1847592."""
    with log.py_warning_filter(
            category=DeprecationWarning,
            message="Using or importing the ABCs from 'collections' instead "
            "of from 'collections.abc' is deprecated", module='bs4.element'):
        yield


def _decompress_gzip_datafile(filename):
    path = os.path.join(abs_datapath(), filename)
    yield from io.TextIOWrapper(gzip.open(path), encoding="utf-8")


def blocked_hosts():
    return _decompress_gzip_datafile("blocked-hosts.gz")


def adblock_dataset_tsv():
    return _decompress_gzip_datafile("brave-adblock/ublock-matches.tsv.gz")


def easylist_txt():
    return _decompress_gzip_datafile("easylist.txt.gz")


def easyprivacy_txt():
    return _decompress_gzip_datafile("easyprivacy.txt.gz")


def _has_qtwebengine() -> bool:
    """Check whether QtWebEngine is available."""
    try:
        from qutebrowser.qt import webenginecore   # pylint: disable=unused-import
    except ImportError:
        return False
    return True


DISABLE_SECCOMP_BPF_FLAG = "--disable-seccomp-filter-sandbox"
DISABLE_SECCOMP_BPF_ARGS = ["-s", "qt.chromium.sandboxing", "disable-seccomp-bpf"]


def _needs_map_discard_workaround(qtwe_version: utils.VersionNumber) -> bool:
    """Check if this system needs the glibc 2.41+ MAP_DISCARD workaround.

    WORKAROUND for https://bugreports.qt.io/browse/QTBUG-134631
    See https://bugs.gentoo.org/show_bug.cgi?id=949654
    """
    if not utils.is_posix:
        return False

    libc_name, libc_version_str = platform.libc_ver()
    if libc_name != "glibc":
        return False

    libc_version = utils.VersionNumber.parse(libc_version_str)
    kernel_version = utils.VersionNumber.parse(os.uname().release)

    # https://sourceware.org/git/?p=glibc.git;a=commit;h=461cab1
    affected_glibc = utils.VersionNumber(2, 41)
    affected_kernel = utils.VersionNumber(6, 11)

    return (
        libc_version >= affected_glibc
        and kernel_version >= affected_kernel
        and not (
            # https://codereview.qt-project.org/c/qt/qtwebengine-chromium/+/631749
            # -> Fixed in QtWebEngine 5.15.9
            utils.VersionNumber(5, 15, 19) <= qtwe_version < utils.VersionNumber(6)
            # https://codereview.qt-project.org/c/qt/qtwebengine-chromium/+/631750
            # -> Fixed in QtWebEngine 6.8.4
            or utils.VersionNumber(6, 8, 4) <= qtwe_version < utils.VersionNumber(6, 9)
            # https://codereview.qt-project.org/c/qt/qtwebengine-chromium/+/631348
            # -> Fixed in QtWebEngine 6.9.1
            or utils.VersionNumber(6, 9, 1) <= qtwe_version
        )
    )


def disable_seccomp_bpf_sandbox() -> bool:
    """Check whether we need to disable the seccomp BPF sandbox.

    This is needed for some QtWebEngine setups, with older Qt versions but
    newer kernels.
    """
    if not _has_qtwebengine():
        return False
    versions = version.qtwebengine_versions(avoid_init=True)
    return (
        versions.webengine == utils.VersionNumber(5, 15, 2)
        or _needs_map_discard_workaround(versions.webengine)
    )


SOFTWARE_RENDERING_FLAG = "--disable-gpu"
SOFTWARE_RENDERING_ARGS = ["-s", "qt.force_software_rendering", "chromium"]


def offscreen_plugin_enabled() -> bool:
    """Check whether offscreen rendering is enabled."""
    # FIXME allow configuring via custom CLI flag?
    return os.environ.get("QT_QPA_PLATFORM") == "offscreen"


def use_software_rendering() -> bool:
    """Check whether to enforce software rendering for tests."""
    return _has_qtwebengine() and offscreen_plugin_enabled()


def import_userscript(name):
    """Import a userscript via importlib.

    This is needed because userscripts don't have a .py extension and violate
    Python's module naming convention.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    script_path = repo_root / 'misc' / 'userscripts' / name
    module_name = name.replace('-', '_')
    loader = importlib.machinery.SourceFileLoader(
        module_name, str(script_path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def enum_members(base, enumtype):
    """Get all members of a Qt enum."""
    if issubclass(enumtype, enum.Enum):
        # PyQt 6
        return {m.name: m for m in enumtype}
    else:
        # PyQt 5
        return {
            name: value
            for name, value in vars(base).items()
            if isinstance(value, enumtype)
        }


def is_userns_restricted() -> Optional[bool]:
    if not utils.is_linux:
        return None

    try:
        proc = subprocess.run(
            ["sysctl", "-n", "kernel.apparmor_restrict_unprivileged_userns"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    return proc.stdout.strip() == "1"
