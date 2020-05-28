# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2019-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

import pytest

from PyQt5.QtCore import QObject

from qutebrowser.config import stylesheet


class StyleObj(QObject):

    def __init__(self, stylesheet=None, parent=None):
        super().__init__(parent)
        if stylesheet is not None:
            self.STYLESHEET = stylesheet  # noqa: N801,N806 pylint: disable=invalid-name
        self.rendered_stylesheet = None

    def setStyleSheet(self, stylesheet):
        self.rendered_stylesheet = stylesheet


def test_get_stylesheet(config_stub):
    config_stub.val.colors.hints.fg = 'magenta'
    observer = stylesheet._StyleSheetObserver(
        StyleObj(), stylesheet="{{ conf.colors.hints.fg }}", update=False)
    assert observer._get_stylesheet() == 'magenta'


@pytest.mark.parametrize('delete', [True, False])
@pytest.mark.parametrize('stylesheet_param', [True, False])
@pytest.mark.parametrize('update', [True, False])
def test_set_register_stylesheet(delete, stylesheet_param, update, qtbot,
                                 config_stub, caplog):
    config_stub.val.colors.hints.fg = 'magenta'
    qss = "{{ conf.colors.hints.fg }}"

    with caplog.at_level(9):  # VDEBUG
        if stylesheet_param:
            obj = StyleObj()
            stylesheet.set_register(obj, qss, update=update)
        else:
            obj = StyleObj(qss)
            stylesheet.set_register(obj, update=update)

    assert caplog.messages[-1] == 'stylesheet for StyleObj: magenta'

    assert obj.rendered_stylesheet == 'magenta'

    if delete:
        with qtbot.waitSignal(obj.destroyed):
            obj.deleteLater()

    config_stub.val.colors.hints.fg = 'yellow'

    expected = 'magenta' if delete or not update else 'yellow'
    assert obj.rendered_stylesheet == expected
