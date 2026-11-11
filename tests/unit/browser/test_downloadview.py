# SPDX-FileCopyrightText: Freya Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qutebrowser.qt.core import QUrl

from qutebrowser.browser import downloads, qtnetworkdownloads, downloadview


class FakeDownload(downloads.AbstractDownloadItem):

    # As this is used for tests, we only override what's actually needed.
    # pylint: disable=abstract-method

    def __init__(self, done: bool, successful: bool = False) -> None:
        super().__init__(manager=None)
        self.done = done
        self.successful = successful

    def url(self) -> QUrl:
        return QUrl('https://example.org/')


@pytest.fixture
def qtnetwork_manager(config_stub, cookiejar_and_cache):
    """A QtNetwork-based download manager."""
    return qtnetworkdownloads.DownloadManager()


@pytest.fixture
def model(qtnetwork_manager, qtmodeltester, qapp):
    """A simple DownloadModel."""
    model = downloads.DownloadModel(qtnetwork_manager)
    qtmodeltester.check(model)
    return model


@pytest.fixture
def view(model, qtbot):
    """A DownloadView."""
    dv = downloadview.DownloadView(model)
    qtbot.add_widget(dv)
    return dv


@pytest.mark.parametrize('finished_downloads, extra_actions', [
    ([FakeDownload(done=True)], [None, "Remove all finished"]),
    ([], []),
])
@pytest.mark.parametrize('item, expected', [
    # Clicking outside of a download item
    (None, []),

    # Clicking a in-progress item
    (FakeDownload(done=False), ["Cancel", "Copy URL"]),

    # Clicking a successful item
    (
        FakeDownload(done=True, successful=True),
        ["Open", "Open directory", "Remove", "Copy URL"],
    ),

    # Clicking an unsuccessful item
    (
        FakeDownload(done=True, successful=False),
        ["Retry", "Remove", "Copy URL"],
    ),
])
def test_get_menu_actions(finished_downloads, extra_actions, item, expected,
                          view, qtnetwork_manager):
    qtnetwork_manager.downloads.extend(finished_downloads)

    actions = view._get_menu_actions(item)
    texts = [action[0] for action in actions]
    assert texts == expected + extra_actions
