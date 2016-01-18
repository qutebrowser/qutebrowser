# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for usertypes.Question."""

import logging

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


def test_mode_invalid(question):
    """Test setting mode to something which is not a PromptMode member."""
    with pytest.raises(TypeError):
        question.mode = 42


@pytest.mark.parametrize('mode, answer, signal_names', [
    (usertypes.PromptMode.text, 'foo', ['answered', 'completed']),
    (usertypes.PromptMode.yesno, True, ['answered', 'completed',
                                        'answered_yes']),
    (usertypes.PromptMode.yesno, False, ['answered', 'completed',
                                         'answered_no']),
])
def test_done(mode, answer, signal_names, question, qtbot):
    """Test the 'done' method and completed/answered signals."""
    question.mode = mode
    question.answer = answer
    signals = [getattr(question, name) for name in signal_names]
    with qtbot.waitSignals(signals):
        question.done()
    assert not question.is_aborted


def test_cancel(question, qtbot):
    """Test Question.cancel()."""
    with qtbot.waitSignals([question.cancelled, question.completed]):
        question.cancel()
    assert not question.is_aborted


def test_abort(question, qtbot):
    """Test Question.abort()."""
    with qtbot.waitSignals([question.aborted, question.completed]):
        question.abort()
    assert question.is_aborted


def test_abort_typeerror(question, qtbot, mocker, caplog):
    """Test Question.abort() with .emit() raising a TypeError."""
    signal_mock = mocker.patch('qutebrowser.utils.usertypes.Question.aborted')
    signal_mock.emit.side_effect = TypeError
    with caplog.at_level(logging.ERROR, 'misc'):
        question.abort()
    assert caplog.records[0].message == 'Error while aborting question'
