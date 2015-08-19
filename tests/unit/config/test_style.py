# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Tests for qutebrowser.config.style."""

import logging

import pytest
from PyQt5.QtCore import QObject
from PyQt5.QtGui import QColor

from qutebrowser.config import style


def test_get_stylesheet(config_stub):
    config_stub.data = {
        'colors': {'completion.bg': 'black'},
        'fonts': {'completion': 'foo'},
        'foo': {'bar': 'baz'},
    }
    template = "{{ color['completion.bg'] }}\n{{ font['completion'] }}"
    rendered = style.get_stylesheet(template)
    assert rendered == 'background-color: black;\nfont: foo;'


class Obj(QObject):

    def __init__(self, stylesheet, parent=None):
        super().__init__(parent)
        self.STYLESHEET = stylesheet  # pylint: disable=invalid-name
        self.rendered_stylesheet = None

    def setStyleSheet(self, stylesheet):
        self.rendered_stylesheet = stylesheet


@pytest.mark.parametrize('delete', [True, False])
def test_set_register_stylesheet(delete, qtbot, config_stub, caplog):
    config_stub.data = {'fonts': {'foo': 'bar'}, 'colors': {}}
    obj = Obj("{{ font['foo'] }}")

    with caplog.atLevel(9):  # VDEBUG
        style.set_register_stylesheet(obj)

    records = caplog.records()
    assert len(records) == 1
    assert records[0].message == 'stylesheet for Obj: font: bar;'

    assert obj.rendered_stylesheet == 'font: bar;'

    if delete:
        with qtbot.waitSignal(obj.destroyed):
            obj.deleteLater()

    config_stub.data = {'fonts': {'foo': 'baz'}, 'colors': {}}
    style.get_stylesheet.cache_clear()
    config_stub.changed.emit('fonts', 'foo')

    if delete:
        expected = 'font: bar;'
    else:
        expected = 'font: baz;'
    assert obj.rendered_stylesheet == expected


class TestColorDict:

    @pytest.mark.parametrize('key, expected', [
        ('foo', 'one'),
        ('foo.fg', 'color: two;'),
        ('foo.bg', 'background-color: three;'),
    ])
    def test_values(self, key, expected):
        d = style.ColorDict()
        d['foo'] = 'one'
        d['foo.fg'] = 'two'
        d['foo.bg'] = 'three'
        assert d[key] == expected

    def test_key_error(self, caplog):
        d = style.ColorDict()
        with caplog.atLevel(logging.ERROR):
            d['foo']  # pylint: disable=pointless-statement
        records = caplog.records()
        assert len(records) == 1
        assert records[0].message == 'No color defined for foo!'

    def test_qcolor(self):
        d = style.ColorDict()
        d['foo'] = QColor()
        with pytest.raises(TypeError):
            d['foo']  # pylint: disable=pointless-statement


@pytest.mark.parametrize('key, expected', [
    ('foo', 'font: one;'),
    ('bar', ''),
])
def test_font_dict(key, expected):
    d = style.FontDict()
    d['foo'] = 'one'
    assert d[key] == expected
