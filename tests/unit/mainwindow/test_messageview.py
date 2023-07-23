# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import contextlib

import pytest
from qutebrowser.qt.core import Qt

from qutebrowser.mainwindow import messageview
from qutebrowser.utils import usertypes, message


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
        view.show_message(message.MessageInfo(level, 'test'))
    assert view._messages[0].isVisible()


def test_message_hiding(qtbot, view):
    """Messages should be hidden after the timer times out."""
    with qtbot.wait_signal(view._clear_timer.timeout):
        view.show_message(message.MessageInfo(usertypes.MessageLevel.info, 'test'))
    assert not view._messages


def test_size_hint(view):
    """The message height should increase with more messages."""
    view.show_message(message.MessageInfo(usertypes.MessageLevel.info, 'test1'))
    height1 = view.sizeHint().height()
    assert height1 > 0
    view.show_message(message.MessageInfo(usertypes.MessageLevel.info, 'test2'))
    height2 = view.sizeHint().height()
    assert height2 == height1 * 2


def test_word_wrap(view, qtbot):
    """A long message should be wrapped."""
    with qtbot.wait_signal(view._clear_timer.timeout):
        view.show_message(message.MessageInfo(usertypes.MessageLevel.info, 'short'))
        assert len(view._messages) == 1
        height1 = view.sizeHint().height()
        assert height1 > 0

    text = ("Athene, the bright-eyed goddess, answered him at once: Father of "
            "us all, Son of Cronos, Highest King, clearly that man deserved to be "
            "destroyed: so let all be destroyed who act as he did. But my heart aches "
            "for Odysseus, wise but ill fated, who suffers far from his friends on an "
            "island deep in the sea.")

    view.show_message(message.MessageInfo(usertypes.MessageLevel.info, text))
    assert len(view._messages) == 1
    height2 = view.sizeHint().height()

    assert height2 > height1
    assert view._messages[0].wordWrap()


@pytest.mark.parametrize("rich, higher, expected_format", [
    (True, True, Qt.TextFormat.RichText),
    (False, False, Qt.TextFormat.PlainText),
    (None, False, Qt.TextFormat.PlainText),
])
@pytest.mark.parametrize("replace", ["test", None])
def test_rich_text(view, qtbot, rich, higher, expected_format, replace):
    """Rich text should be rendered appropriately.

    This makes sure the title has been rendered as plain text by comparing the
    heights of the two widgets. To ensure consistent results, we disable word-wrapping.
    """
    level = usertypes.MessageLevel.info
    text = 'with <h1>markup</h1>'
    text2 = 'with <h1>markup</h1> 2'

    info1 = message.MessageInfo(level, text, replace=replace)
    info2 = message.MessageInfo(level, text2, replace=replace, rich=rich)

    ctx = (
        qtbot.wait_signal(view._clear_timer.timeout) if replace is None
        else contextlib.nullcontext()
    )
    with ctx:
        view.show_message(info1)
        assert len(view._messages) == 1
        view._messages[0].setWordWrap(False)

        height1 = view.sizeHint().height()
        assert height1 > 0

        assert view._messages[0].textFormat() == Qt.TextFormat.PlainText  # default

    view.show_message(info2)
    assert len(view._messages) == 1
    view._messages[0].setWordWrap(False)

    height2 = view.sizeHint().height()
    assert height2 > 0

    assert view._messages[0].textFormat() == expected_format

    if higher:
        assert height2 > height1
    else:
        assert height2 == height1


@pytest.mark.parametrize("info1, info2, count", [
    # same
    (
        message.MessageInfo(usertypes.MessageLevel.info, 'test'),
        message.MessageInfo(usertypes.MessageLevel.info, 'test'),
        1,
    ),
    # different text
    (
        message.MessageInfo(usertypes.MessageLevel.info, 'test'),
        message.MessageInfo(usertypes.MessageLevel.info, 'test2'),
        2,
    ),
    # different level
    (
        message.MessageInfo(usertypes.MessageLevel.info, 'test'),
        message.MessageInfo(usertypes.MessageLevel.error, 'test'),
        2,
    ),
    # different rich text
    (
        message.MessageInfo(usertypes.MessageLevel.info, 'test', rich=True),
        message.MessageInfo(usertypes.MessageLevel.info, 'test', rich=False),
        2,
    ),
    # different replaces
    (
        message.MessageInfo(usertypes.MessageLevel.info, 'test'),
        message.MessageInfo(usertypes.MessageLevel.info, 'test', replace='test'),
        2,
    ),
])
def test_show_message_twice(view, info1, info2, count):
    """Show the exact same message twice -> only one should be shown."""
    view.show_message(info1)
    view.show_message(info2)
    assert len(view._messages) == count


def test_show_message_twice_after_first_disappears(qtbot, view):
    """Show the same message twice after the first is gone."""
    with qtbot.wait_signal(view._clear_timer.timeout):
        view.show_message(message.MessageInfo(usertypes.MessageLevel.info, 'test'))
    # Just a sanity check
    assert not view._messages

    view.show_message(message.MessageInfo(usertypes.MessageLevel.info, 'test'))
    assert len(view._messages) == 1


def test_changing_timer_with_messages_shown(qtbot, view, config_stub):
    """When we change messages.timeout, the timer should be restarted."""
    config_stub.val.messages.timeout = 900000  # 15s
    view.show_message(message.MessageInfo(usertypes.MessageLevel.info, 'test'))
    with qtbot.wait_signal(view._clear_timer.timeout):
        config_stub.val.messages.timeout = 100


@pytest.mark.parametrize('count, expected', [(1, 100), (3, 300),
                                             (5, 500), (7, 500)])
def test_show_multiple_messages_longer(view, count, expected):
    """When there are multiple messages, messages should be shown longer.

    There is an upper maximum to avoid messages never disappearing.
    """
    for message_number in range(1, count+1):
        view.show_message(message.MessageInfo(
            usertypes.MessageLevel.info, f"test {message_number}"))
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
    view.show_message(message.MessageInfo(
        usertypes.MessageLevel.info, 'test', replace=replace1))
    view.show_message(message.MessageInfo(
        usertypes.MessageLevel.info, 'test 2', replace=replace2))
    assert len(view._messages) == length


def test_replacing_different_severity(view):
    view.show_message(message.MessageInfo(
        usertypes.MessageLevel.info, 'test', replace='testid'))
    with pytest.raises(AssertionError):
        view.show_message(message.MessageInfo(
            usertypes.MessageLevel.error, 'test 2', replace='testid'))


def test_replacing_changed_text(view):
    view.show_message(message.MessageInfo(
        usertypes.MessageLevel.info, 'test', replace='testid'))
    view.show_message(message.MessageInfo(
        usertypes.MessageLevel.info, 'test 2'))
    view.show_message(message.MessageInfo(
        usertypes.MessageLevel.info, 'test 3', replace='testid'))
    assert len(view._messages) == 2
    assert view._messages[0].text() == 'test 3'
    assert view._messages[1].text() == 'test 2'


def test_replacing_geometry(qtbot, view):
    view.show_message(message.MessageInfo(
        usertypes.MessageLevel.info, 'test', replace='testid'))

    with qtbot.wait_signal(view.update_geometry):
        view.show_message(message.MessageInfo(
            usertypes.MessageLevel.info, 'test 2', replace='testid'))


@pytest.mark.parametrize('button, count', [
    (Qt.MouseButton.LeftButton, 0),
    (Qt.MouseButton.MiddleButton, 0),
    (Qt.MouseButton.RightButton, 0),
    (Qt.MouseButton.BackButton, 2),
])
def test_click_messages(qtbot, view, button, count):
    """Messages should disappear when we click on them."""
    view.show_message(message.MessageInfo(
        usertypes.MessageLevel.info, 'test mouse click'))
    view.show_message(message.MessageInfo(
        usertypes.MessageLevel.info, 'test mouse click 2'))
    qtbot.mousePress(view, button)
    assert len(view._messages) == count
