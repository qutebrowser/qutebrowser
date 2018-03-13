# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

from unittest import mock

from PyQt5.QtCore import QUrl

import pytest

from qutebrowser.commands import cmdexc
from qutebrowser.browser import commands, urlmarks
from qutebrowser.mainwindow import tabbedbrowser

pytestmark = pytest.mark.usefixtures('redirect_webengine_data')

@pytest.fixture
def tabbed_browser():
    return mock.Mock(spec=tabbedbrowser.TabbedBrowser)

@pytest.fixture
def command_dispatcher(tabbed_browser, config_stub):
    config_stub.auto_search = 'never'
    return commands.CommandDispatcher(0, tabbed_browser)


class TestBookmarkAdd:

    def test_add(self, command_dispatcher, bookmark_manager_mock):
        command_dispatcher.bookmark_add('example.com', 'Example Site')
        bookmark_manager_mock.add.assert_called_with(
            QUrl('http://example.com'), 'Example Site', [], toggle=False)

    def test_no_url_or_title(self, command_dispatcher, tabbed_browser,
                             bookmark_manager_mock):
        tab = mock.Mock()
        tab.title.return_value = 'Example Site'
        tabbed_browser.currentWidget.return_value = tab
        tabbed_browser.current_url.return_value = QUrl('example.com')
        command_dispatcher.bookmark_add()
        bookmark_manager_mock.add.assert_called_with(
            QUrl('example.com'), 'Example Site', [], toggle=False)

    def test_no_title(self, command_dispatcher, tabbed_browser,
                      bookmark_manager_mock):
        with pytest.raises(cmdexc.CommandError) as excinfo:
            command_dispatcher.bookmark_add('example.com')
        assert str(excinfo.value) == \
            'Title must be provided if url has been provided'

    def test_dupe(self, command_dispatcher, bookmark_manager_mock):
        bookmark_manager_mock.add.side_effect = urlmarks.AlreadyExistsError
        with pytest.raises(cmdexc.CommandError):
            command_dispatcher.bookmark_add('example.com', 'Example Site')

    def test_toggle_on(self, command_dispatcher, bookmark_manager_mock,
                       message_mock):
        bookmark_manager_mock.add.return_value = True
        command_dispatcher.bookmark_add('example.com', 'Example Site', toggle=True)
        bookmark_manager_mock.add.assert_called_with(
            QUrl('http://example.com'), 'Example Site', [], toggle=True)
        assert message_mock.getmsg().text == 'Bookmarked http://example.com'

    def test_toggle_off(self, command_dispatcher, bookmark_manager_mock,
                        message_mock):
        bookmark_manager_mock.add.return_value = False
        command_dispatcher.bookmark_add('example.com', 'Example Site', toggle=True)
        bookmark_manager_mock.add.assert_called_with(
            QUrl('http://example.com'), 'Example Site', [], toggle=True)
        assert message_mock.getmsg().text == 'Removed bookmark http://example.com'


class TestBookmarkTag:

    def test_append(self, command_dispatcher, bookmark_manager_mock):
        bookmark_manager_mock.get.return_value = urlmarks.Bookmark(
            url=QUrl('http://example.com'),
            title='Example',
            tags=['foo']
        )

        command_dispatcher.bookmark_tag('http://example.com', 'bar', 'baz')

        bookmark_manager_mock.get.assert_called_with(
            QUrl('http://example.com'))
        bookmark_manager_mock.update.assert_called_with(urlmarks.Bookmark(
            url=QUrl('http://example.com'),
            title='Example',
            tags=['foo', 'bar', 'baz']
        ))

    def test_remove(self, command_dispatcher, bookmark_manager_mock):
        bookmark_manager_mock.get.return_value = urlmarks.Bookmark(
            url=QUrl('http://example.com'),
            title='Example',
            tags=['foo', 'bar', 'baz']
        )
        command_dispatcher.bookmark_tag(
            'http://example.com', 'foo', 'baz', remove=True)
        bookmark_manager_mock.get.assert_called_with(
            QUrl('http://example.com'))
        bookmark_manager_mock.update.assert_called_with(urlmarks.Bookmark(
            url=QUrl('http://example.com'),
            title='Example',
            tags=['bar']
        ))

    def test_nonexistant(self, command_dispatcher, bookmark_manager_mock):
        bookmark_manager_mock.get.return_value = None

        with pytest.raises(cmdexc.CommandError) as excinfo:
            command_dispatcher.bookmark_tag('http://example.com', 'foo')

        assert str(excinfo.value) == \
                'Bookmark http://example.com does not exist'
        bookmark_manager_mock.get.assert_called_with(
            QUrl('http://example.com'))


class TestBookmarkLoad:

    def test_no_tags(self, command_dispatcher):
        with pytest.raises(cmdexc.CommandError) as excinfo:
            command_dispatcher.bookmark_load()
        assert str(excinfo.value) == 'No tags provided'

    @pytest.mark.parametrize('delete', [True, False])
    def test_open(self, command_dispatcher, bookmark_manager_mock,
                  tabbed_browser, delete):
        tab = mock.Mock()
        tabbed_browser.currentWidget.return_value = tab
        bookmark_manager_mock.get_tagged.return_value = [
            urlmarks.Bookmark(url='example.com/1', title='', tags=[]),
            urlmarks.Bookmark(url='example.com/2', title='', tags=[]),
        ]

        command_dispatcher.bookmark_load('foo', delete=delete)

        bookmark_manager_mock.get_tagged.assert_called_once_with(('foo',))
        tab.openurl.assert_called_once_with(QUrl('example.com/1'))

        if delete:
            bookmark_manager_mock.delete.assert_called_once_with(
                'example.com/1'
            )

    @pytest.mark.parametrize('in_args, out_args', [
        ({'tab': True}, {'background': False, 'related': False}),
        ({'bg': True}, {'background': True, 'related': False}),
    ])
    @pytest.mark.parametrize('open_all', [True, False])
    @pytest.mark.parametrize('delete', [True, False])
    def test_open_tab(self, command_dispatcher, bookmark_manager_mock,
                      tabbed_browser, in_args, out_args, open_all, delete):
        bookmark_manager_mock.get_tagged.return_value = [
            urlmarks.Bookmark(url='example.com/1', title='', tags=[]),
            urlmarks.Bookmark(url='example.com/2', title='', tags=[]),
            urlmarks.Bookmark(url='example.com/3', title='', tags=[]),
        ]

        command_dispatcher.bookmark_load('foo', open_all=open_all,
                                         delete=delete, **in_args)

        bookmark_manager_mock.get_tagged.assert_called_once_with(('foo',))
        if open_all:
            tabbed_browser.tabopen.assert_has_calls([
                mock.call(QUrl('example.com/1'), **out_args),
                mock.call(QUrl('example.com/2'), **out_args),
                mock.call(QUrl('example.com/3'), **out_args),
            ])
            if delete:
                bookmark_manager_mock.delete.assert_has_calls([
                    mock.call('example.com/1'),
                    mock.call('example.com/2'),
                    mock.call('example.com/3'),
            ])
        else:
            tabbed_browser.tabopen.assert_called_once_with(
                QUrl('example.com/1'), **out_args,
            )
            if delete:
                bookmark_manager_mock.delete.assert_called_once_with(
                    'example.com/1'
                )

    @pytest.mark.parametrize('private', [True, False])
    def test_open_window(self, command_dispatcher, bookmark_manager_mock,
                         mocker, tabbed_browser, private):
        tabbed_browser.private = private
        m = mocker.patch('qutebrowser.browser.commands.mainwindow.MainWindow')
        bookmark_manager_mock.get_tagged.return_value = [
            urlmarks.Bookmark(url='example.com/1', title='', tags=[]),
            urlmarks.Bookmark(url='example.com/2', title='', tags=[]),
        ]

        command_dispatcher.bookmark_load('foo', window=True)

        m.assert_called_once_with(private=private)

    @pytest.mark.parametrize('args', [
        {'tab': True, 'bg': True},
        {'tab': True, 'window': True},
        {'bg': True, 'window': True},
    ])
    def test_invalid(self, command_dispatcher, bookmark_manager_mock, args):
        bookmark_manager_mock.get_tagged.return_value = [
            urlmarks.Bookmark(url='example.com/1', title='', tags=[])
        ]

        with pytest.raises(cmdexc.CommandError) as excinfo:
            command_dispatcher.bookmark_load('foo', **args)
        assert str(excinfo.value) == 'Only one of -t/-b/-w/-p can be given!'


    def test_open_all_invalid(self, command_dispatcher):
        with pytest.raises(cmdexc.CommandError) as excinfo:
            command_dispatcher.bookmark_load('foo', open_all=True)
        assert str(excinfo.value) == '-a requires one of -t/-b/-w'
