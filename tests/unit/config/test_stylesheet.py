# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


import pytest

from qutebrowser.qt.core import QObject

from qutebrowser.config import stylesheet


class StyleObj(QObject):

    def __init__(self, stylesheet=None, parent=None):
        super().__init__(parent)
        if stylesheet is not None:
            self.STYLESHEET = stylesheet
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
@pytest.mark.parametrize('changed_option', ['colors.hints.fg', 'colors.hints.bg'])
def test_set_register_stylesheet(delete, stylesheet_param, update, changed_option,
                                 qtbot, config_stub, caplog):
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
        with qtbot.wait_signal(obj.destroyed):
            obj.deleteLater()

    config_stub.set_obj(changed_option, 'yellow')

    expected = ('magenta' if delete or not update or changed_option != 'colors.hints.fg'
                else 'yellow')
    assert obj.rendered_stylesheet == expected
