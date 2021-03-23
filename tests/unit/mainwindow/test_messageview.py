# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import pytest
from PyQt5.QtCore import Qt

from qutebrowser.mainwindow import messageview
from qutebrowser.utils import usertypes


@pytest.fixture
def view(qtbot, config_stub):
    config_stub.val.messages.timeout = 100
    mv = messageview.MessageView()
    qtbot.add_widget(mv)
    return mv


@pytest.mark.parametrize('level', [usertypes.MessageLevel.info,
                                   usertypes.MessageLevel.warning,
                                   usertypes.MessageLevel.error])
@pytest.mark.flaky  # on macOS
def test_single_message(qtbot, view, level):
    with qtbot.wait_exposed(view, timeout=5000):
        view.show_message(level, 'test')
    assert view._messages[0].isVisible()


def test_message_hiding(qtbot, view):
    """Messages should be hidden after the timer times out."""
    with qtbot.wait_signal(view._clear_timer.timeout):
        view.show_message(usertypes.MessageLevel.info, 'test')
    assert not view._messages


def test_size_hint(view):
    """The message height should increase with more messages."""
    view.show_message(usertypes.MessageLevel.info, 'test1')
    height1 = view.sizeHint().height()
    assert height1 > 0
    view.show_message(usertypes.MessageLevel.info, 'test2')
    height2 = view.sizeHint().height()
    assert height2 == height1 * 2


def test_word_wrap(view, qtbot):
    """A long message should be wrapped."""
    with qtbot.wait_signal(view._clear_timer.timeout):
        view.show_message(usertypes.MessageLevel.info, 'short')
        height1 = view.sizeHint().height()
        assert height1 > 0

    text = ("Athene, the bright-eyed goddess, answered him at once: Father of "
            "us all, Son of Cronos, Highest King, clearly that man deserved to be "
            "destroyed: so let all be destroyed who act as he did. But my heart aches "
            "for Odysseus, wise but ill fated, who suffers far from his friends on an "
            "island deep in the sea.")

    view.show_message(usertypes.MessageLevel.info, text)
    height2 = view.sizeHint().height()

    assert height2 > height1
    assert view._messages[0].wordWrap()


def test_show_message_twice(view):
    """Show the same message twice -> only one should be shown."""
    view.show_message(usertypes.MessageLevel.info, 'test')
    view.show_message(usertypes.MessageLevel.info, 'test')
    assert len(view._messages) == 1


def test_show_message_twice_after_first_disappears(qtbot, view):
    """Show the same message twice after the first is gone."""
    with qtbot.wait_signal(view._clear_timer.timeout):
        view.show_message(usertypes.MessageLevel.info, 'test')
    # Just a sanity check
    assert not view._messages

    view.show_message(usertypes.MessageLevel.info, 'test')
    assert len(view._messages) == 1


def test_changing_timer_with_messages_shown(qtbot, view, config_stub):
    """When we change messages.timeout, the timer should be restarted."""
    config_stub.val.messages.timeout = 900000  # 15s
    view.show_message(usertypes.MessageLevel.info, 'test')
    with qtbot.wait_signal(view._clear_timer.timeout):
        config_stub.val.messages.timeout = 100


@pytest.mark.parametrize('count, expected', [(1, 100), (3, 300),
                                             (5, 500), (7, 500)])
def test_show_multiple_messages_longer(view, count, expected):
    """When there are multiple messages, messages should be shown longer.

    There is an upper maximum to avoid messages never disappearing.
    """
    for message_number in range(1, count+1):
        view.show_message(usertypes.MessageLevel.info,
                          'test ' + str(message_number))
    assert view._clear_timer.interval() == expected


@pytest.mark.parametrize('replace1, replace2, length', [
    (None, None, 2),    # Two stacked messages
    ('testid', 'testid', 1),  # Two replaceable messages
    (None, 'testid', 2),  # Stacked and replaceable
    ('testid', None, 2),  # Replaceable and stacked
    ('testid1', 'testid2', 2),  # Different IDs
])
def test_replaced_messages(view, replace1, replace2, length):
    """Show two stack=False messages which should replace each other."""
    view.show_message(usertypes.MessageLevel.info, 'test', replace=replace1)
    view.show_message(usertypes.MessageLevel.info, 'test 2', replace=replace2)
    assert len(view._messages) == length


def test_replacing_different_severity(view):
    view.show_message(usertypes.MessageLevel.info, 'test', replace='testid')
    with pytest.raises(AssertionError):
        view.show_message(usertypes.MessageLevel.error, 'test 2', replace='testid')


def test_replacing_changed_text(view):
    view.show_message(usertypes.MessageLevel.info, 'test', replace='testid')
    view.show_message(usertypes.MessageLevel.info, 'test 2')
    view.show_message(usertypes.MessageLevel.info, 'test 3', replace='testid')
    assert len(view._messages) == 2
    assert view._messages[0].text() == 'test 3'
    assert view._messages[1].text() == 'test 2'


def test_replacing_geometry(qtbot, view):
    view.show_message(usertypes.MessageLevel.info, 'test', replace='testid')

    with qtbot.wait_signal(view.update_geometry):
        view.show_message(usertypes.MessageLevel.info, 'test 2', replace='testid')


@pytest.mark.parametrize('button, count', [
    (Qt.LeftButton, 0),
    (Qt.MiddleButton, 0),
    (Qt.RightButton, 0),
    (Qt.BackButton, 2),
])
def test_click_messages(qtbot, view, button, count):
    """Messages should disappear when we click on them."""
    view.show_message(usertypes.MessageLevel.info, 'test mouse click')
    view.show_message(usertypes.MessageLevel.info, 'test mouse click 2')
    qtbot.mousePress(view, button)
    assert len(view._messages) == count
