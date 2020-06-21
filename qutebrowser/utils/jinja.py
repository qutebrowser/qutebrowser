# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Utilities related to jinja2."""

import os
import os.path
import typing
import functools
import contextlib
import html

import jinja2
import jinja2.nodes
from PyQt5.QtCore import QUrl

from qutebrowser.utils import utils, urlutils, log, qtutils, javascript
from qutebrowser.misc import debugcachestats


html_fallback = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Error while loading template</title>
  </head>
  <body>
    <p><span style="font-size:120%;color:red">
    The %FILE% template could not be found!<br>
    Please check your qutebrowser installation
      </span><br>
      %ERROR%
    </p>
  </body>
</html>
"""


class Loader(jinja2.BaseLoader):

    """Jinja loader which uses utils.read_file to load templates.

    Attributes:
        _subdir: The subdirectory to find templates in.
    """

    def __init__(self, subdir: str) -> None:
        self._subdir = subdir

    def get_source(
            self,
            _env: jinja2.Environment,
            template: str
    ) -> typing.Tuple[str, str, typing.Callable[[], bool]]:
        path = os.path.join(self._subdir, template)
        try:
            source = utils.read_file(path)
        except OSError as e:
            source = html_fallback.replace("%ERROR%", html.escape(str(e)))
            source = source.replace("%FILE%", html.escape(template))
            log.misc.exception("The {} template could not be loaded from {}"
                               .format(template, path))
        # Currently we don't implement auto-reloading, so we always return True
        # for up-to-date.
        return source, path, lambda: True


class Environment(jinja2.Environment):

    """Our own jinja environment which is more strict."""

    def __init__(self) -> None:
        super().__init__(loader=Loader('html'),
                         autoescape=lambda _name: self._autoescape,
                         undefined=jinja2.StrictUndefined)
        self.globals['resource_url'] = self._resource_url
        self.globals['file_url'] = urlutils.file_url
        self.globals['data_url'] = self._data_url
        self.globals['qcolor_to_qsscolor'] = qtutils.qcolor_to_qsscolor
        self.filters['js_string_escape'] = javascript.string_escape
        self._autoescape = True

    @contextlib.contextmanager
    def no_autoescape(self) -> typing.Iterator[None]:
        """Context manager to temporarily turn off autoescaping."""
        self._autoescape = False
        yield
        self._autoescape = True

    def _resource_url(self, path: str) -> str:
        """Load images from a relative path (to qutebrowser).

        Arguments:
            path: The relative path to the image
        """
        image = utils.resource_filename(path)
        url = QUrl.fromLocalFile(image)
        urlstr = url.toString(QUrl.FullyEncoded)  # type: ignore[arg-type]
        return urlstr

    def _data_url(self, path: str) -> str:
        """Get a data: url for the broken qutebrowser logo."""
        data = utils.read_file(path, binary=True)
        filename = utils.resource_filename(path)
        mimetype = utils.guess_mimetype(filename)
        return urlutils.data_url(mimetype, data).toString()

    def getattr(self, obj: typing.Any, attribute: str) -> typing.Any:
        """Override jinja's getattr() to be less clever.

        This means it doesn't fall back to __getitem__, and it doesn't hide
        AttributeError.
        """
        return getattr(obj, attribute)


def render(template: str, **kwargs: typing.Any) -> str:
    """Render the given template and pass the given arguments to it."""
    return environment.get_template(template).render(**kwargs)


environment = Environment()
js_environment = jinja2.Environment(loader=Loader('javascript'))


@debugcachestats.register()
@functools.lru_cache()
def template_config_variables(template: str) -> typing.FrozenSet[str]:
    """Return the config variables used in the template."""
    unvisted_nodes = [environment.parse(template)]
    result = set()  # type: typing.Set[str]
    while unvisted_nodes:
        node = unvisted_nodes.pop()
        if not isinstance(node, jinja2.nodes.Getattr):
            unvisted_nodes.extend(node.iter_child_nodes())
            continue

        # List of attribute names in reverse order.
        # For example it's ['ab', 'c', 'd'] for 'conf.d.c.ab'.
        attrlist = []  # type: typing.List[str]
        while isinstance(node, jinja2.nodes.Getattr):
            attrlist.append(node.attr)  # type: ignore[attr-defined]
            node = node.node  # type: ignore[attr-defined]

        if isinstance(node, jinja2.nodes.Name):
            if node.name == 'conf':  # type: ignore[attr-defined]
                result.add('.'.join(reversed(attrlist)))
            # otherwise, the node is a Name node so it doesn't have any
            # child nodes
        else:
            unvisted_nodes.append(node)

    from qutebrowser.config import config
    for option in result:
        config.instance.ensure_has_opt(option)

    return frozenset(result)
