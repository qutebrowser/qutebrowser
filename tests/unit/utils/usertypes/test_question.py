# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for usertypes.Question."""

import pytest

from qutebrowser.utils import usertypes


@pytest.fixture
def question():
    return usertypes.Question()


def test_attributes(question):
    """Test setting attributes."""
    question.default = True
    question.text = "foo"


def test_mode(question):
    """Test setting mode to valid members."""
    question.mode = usertypes.PromptMode.yesno
    assert question.mode == usertypes.PromptMode.yesno


@pytest.mark.parametrize('mode, answer, signal_names', [
    (usertypes.PromptMode.text, 'foo', ['answered', 'completed']),
    (usertypes.PromptMode.yesno, True, ['answered', 'answered_yes',
                                        'completed']),
    (usertypes.PromptMode.yesno, False, ['answered', 'answered_no',
                                         'completed']),
])
def test_done(mode, answer, signal_names, question, qtbot):
    """Test the 'done' method and completed/answered signals."""
    question.mode = mode
    question.answer = answer
    signals = [getattr(question, name) for name in signal_names]
    with qtbot.wait_signals(signals, order='strict'):
        question.done()
    assert not question.is_aborted


def test_cancel(question, qtbot):
    """Test Question.cancel()."""
    with qtbot.wait_signals([question.cancelled, question.completed],
                           order='strict'):
        question.cancel()
    assert not question.is_aborted


def test_abort(question, qtbot):
    """Test Question.abort()."""
    with qtbot.wait_signals([question.aborted, question.completed],
                           order='strict'):
        question.abort()
    assert question.is_aborted


def test_abort_twice(question, qtbot):
    """Abort a question twice."""
    with qtbot.wait_signal(question.aborted):
        question.abort()
    assert question.is_aborted
    with qtbot.assert_not_emitted(question.aborted):
        question.abort()
