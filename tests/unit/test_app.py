# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the qutebrowser.app module."""

from qutebrowser.qt.core import QBuffer

from qutebrowser.misc import objects
from qutebrowser import app


def test_on_focus_changed_issue1484(monkeypatch, qapp, caplog):
    """Check what happens when on_focus_changed is called with wrong args.

    For some reason, Qt sometimes calls on_focus_changed() with a QBuffer as
    argument. Let's make sure we handle that gracefully.
    """
    monkeypatch.setattr(objects, 'qapp', qapp)

    buf = QBuffer()
    app.on_focus_changed(buf, buf)

    expected = "on_focus_changed called with non-QWidget {!r}".format(buf)
    assert caplog.messages == [expected]
