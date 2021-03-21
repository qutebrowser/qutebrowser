# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for misc.userscripts.qute-lastpass."""

import json
import dataclasses
from types import SimpleNamespace
from unittest.mock import ANY, call

import pytest

from helpers import testutils

qute_lastpass = testutils.import_userscript('qute-lastpass')

default_lpass_match = [
    {
        "id": "12345",
        "name": "www.example.com",
        "username": "fake@fake.com",
        "password": "foobar",
        "url": "https://www.example.com",
    }
]


@dataclasses.dataclass
class FakeOutput:

    stdout: bytes = b''
    stderr: bytes = b''

    @classmethod
    def json(cls, obj):
        """Get a FakeOutput for a json-encoded object."""
        return cls(stdout=json.dumps(obj).encode('ascii'))


@pytest.fixture
def subprocess_mock(mocker):
    return mocker.patch('subprocess.run')


@pytest.fixture
def qutecommand_mock(mocker):
    return mocker.patch.object(qute_lastpass, 'qute_command')


@pytest.fixture
def stderr_mock(mocker):
    return mocker.patch.object(qute_lastpass, 'stderr')


# Default arguments passed to qute-lastpass
@pytest.fixture
def arguments_mock():
    arguments = SimpleNamespace()
    arguments.url = ''
    arguments.dmenu_invocation = 'rofi -dmenu'
    arguments.insert_mode = True
    arguments.io_encoding = 'UTF-8'
    arguments.merge_candidates = False
    arguments.password_only = False
    arguments.username_only = False
    arguments.no_tld_download = True

    return arguments


class TestQuteLastPassComponents:
    """Test qute-lastpass components."""

    def test_fake_key_raw(self, qutecommand_mock):
        """Test if fake_key_raw properly escapes characters."""
        qute_lastpass.fake_key_raw('john.<<doe>>@example.com ')

        qutecommand_mock.assert_called_once_with(
            'fake-key \\j\\o\\h\\n\\.<less><less>\\d\\o\\e<greater><greater>\\@'
            '\\e\\x\\a\\m\\p\\l\\e\\.\\c\\o\\m" "'
        )

    def test_dmenu(self, subprocess_mock):
        """Test if dmenu command receives properly formatted lpass entries."""
        entries = [
            "1234 | example.com | https://www.example.com | john.doe@example.com",
            "2345 | example2.com | https://www.example2.com | jane.doe@example.com",
        ]

        subprocess_mock.return_value = FakeOutput(stdout=entries[1].encode('ascii'))

        selected = qute_lastpass.dmenu(entries, 'rofi -dmenu', 'UTF-8')

        subprocess_mock.assert_called_once_with(
            ['rofi', '-dmenu'],
            input='\n'.join(entries).encode(),
            stdout=ANY)

        assert selected == entries[1]

    def test_pass_subprocess_args(self, subprocess_mock):
        """Test if pass_ calls subprocess with correct arguments."""
        subprocess_mock.return_value = FakeOutput(stdout=b'[{}]')

        qute_lastpass.pass_('example.com', 'utf-8')

        subprocess_mock.assert_called_once_with(
            ['lpass', 'show', '-x', '-j', '-G', '\\bexample\\.com'],
            stdout=ANY, stderr=ANY)

    def test_pass_returns_candidates(self, subprocess_mock):
        """Test if pass_ returns expected lpass site entry."""
        subprocess_mock.return_value = FakeOutput.json(default_lpass_match)

        response = qute_lastpass.pass_('www.example.com', 'utf-8')
        assert response[1] == ''

        candidates = response[0]

        assert len(candidates) == 1
        assert candidates[0] == default_lpass_match[0]

    def test_pass_no_accounts(self, subprocess_mock):
        """Test if pass_ handles no accounts as an empty lpass result."""
        error_message = b'Error: Could not find specified account(s).'
        subprocess_mock.return_value = FakeOutput(stderr=error_message)

        response = qute_lastpass.pass_('www.example.com', 'utf-8')
        assert response[0] == []
        assert response[1] == ''

    def test_pass_returns_error(self, subprocess_mock):
        """Test if pass_ returns error from lpass."""
        error_message = ('Error: Could not find decryption key. '
                         'Perhaps you need to login with `lpass login`.')
        subprocess_mock.return_value = FakeOutput(stderr=error_message.encode('ascii'))

        response = qute_lastpass.pass_('www.example.com', 'utf-8')
        assert response[0] == []
        assert response[1] == error_message


class TestQuteLastPassMain:
    """Test qute-lastpass main."""

    def test_main_happy_path(self, subprocess_mock, arguments_mock,
                             qutecommand_mock):
        """Test sending username/password to qutebrowser on *single* match."""
        subprocess_mock.return_value = FakeOutput.json(default_lpass_match)

        arguments_mock.url = default_lpass_match[0]['url']
        exit_code = qute_lastpass.main(arguments_mock)

        assert exit_code == qute_lastpass.ExitCodes.SUCCESS

        qutecommand_mock.assert_has_calls([
            call('fake-key \\f\\a\\k\\e\\@\\f\\a\\k\\e\\.\\c\\o\\m'),
            call('fake-key <Tab>'),
            call('fake-key \\f\\o\\o\\b\\a\\r'),
            call('mode-enter insert')
        ])

    def test_main_no_candidates(self, subprocess_mock, arguments_mock,
                                stderr_mock,
                                qutecommand_mock):
        """Test correct exit code and message returned on no entries."""
        error_message = b'Error: Could not find specified account(s).'
        subprocess_mock.return_value = FakeOutput(stderr=error_message)

        arguments_mock.url = default_lpass_match[0]['url']
        exit_code = qute_lastpass.main(arguments_mock)

        assert exit_code == qute_lastpass.ExitCodes.NO_PASS_CANDIDATES
        stderr_mock.assert_called_with(
            "No pass candidates for URL 'https://www.example.com' found!")
        qutecommand_mock.assert_not_called()

    def test_main_lpass_failure(self, subprocess_mock, arguments_mock,
                                stderr_mock,
                                qutecommand_mock):
        """Test correct exit code and message on lpass failure."""
        error_message = (b'Error: Could not find decryption key. '
                         b'Perhaps you need to login with `lpass login`.')
        subprocess_mock.return_value = FakeOutput(stderr=error_message)

        arguments_mock.url = default_lpass_match[0]['url']
        exit_code = qute_lastpass.main(arguments_mock)

        assert exit_code == qute_lastpass.ExitCodes.FAILURE
        # pylint: disable=line-too-long
        stderr_mock.assert_called_with(
            "LastPass CLI returned for www.example.com - Error: Could not find decryption key. Perhaps you need to login with `lpass login`.")
        qutecommand_mock.assert_not_called()

    def test_main_username_only_flag(self, subprocess_mock, arguments_mock,
                                     qutecommand_mock):
        """Test if --username-only flag sends username only."""
        subprocess_mock.return_value = FakeOutput.json(default_lpass_match)

        arguments_mock.url = default_lpass_match[0]['url']
        arguments_mock.username_only = True
        qute_lastpass.main(arguments_mock)

        qutecommand_mock.assert_has_calls([
            call('fake-key \\f\\a\\k\\e\\@\\f\\a\\k\\e\\.\\c\\o\\m'),
            call('mode-enter insert')
        ])

    def test_main_password_only_flag(self, subprocess_mock, arguments_mock,
                                     qutecommand_mock):
        """Test if --password-only flag sends password only."""
        subprocess_mock.return_value = FakeOutput.json(default_lpass_match)

        arguments_mock.url = default_lpass_match[0]['url']
        arguments_mock.password_only = True
        qute_lastpass.main(arguments_mock)

        qutecommand_mock.assert_has_calls([
            call('fake-key \\f\\o\\o\\b\\a\\r'),
            call('mode-enter insert')
        ])

    def test_main_multiple_candidates(self, subprocess_mock, arguments_mock,
                                      qutecommand_mock):
        """Test dmenu-invocation when lpass returns multiple candidates."""
        multiple_matches = default_lpass_match.copy()
        multiple_matches.append(
            {
                "id": "23456",
                "name": "Sites/www.example.com",
                "username": "john.doe@fake.com",
                "password": "barfoo",
                "url": "https://www.example.com",
            }
        )

        lpass_response = FakeOutput.json(multiple_matches)
        dmenu_response = FakeOutput(
            stdout=b'23456 | Sites/www.example.com | https://www.example.com | john.doe@fake.com')

        subprocess_mock.side_effect = [lpass_response, dmenu_response]

        arguments_mock.url = multiple_matches[0]['url']
        exit_code = qute_lastpass.main(arguments_mock)

        assert exit_code == qute_lastpass.ExitCodes.SUCCESS

        subprocess_mock.assert_has_calls([
            call(['lpass', 'show', '-x', '-j', '-G', '\\bwww\\.example\\.com'],
                 stdout=ANY, stderr=ANY),
            call(['rofi', '-dmenu'],
                 input=b'12345 | www.example.com | https://www.example.com | fake@fake.com\n23456 | Sites/www.example.com | https://www.example.com | john.doe@fake.com',
                 stdout=ANY)
        ])

        qutecommand_mock.assert_has_calls([
            call(
                'fake-key \\j\\o\\h\\n\\.\\d\\o\\e\\@\\f\\a\\k\\e\\.\\c\\o\\m'),
            call('fake-key <Tab>'),
            call('fake-key \\b\\a\\r\\f\\o\\o'),
            call('mode-enter insert')
        ])

    def test_main_merge_candidates(self, subprocess_mock, arguments_mock,
                                   qutecommand_mock):
        """Test merge of multiple responses from lpass."""
        fqdn_matches = default_lpass_match.copy()
        fqdn_matches.append(
            {
                "id": "23456",
                "name": "Sites/www.example.com",
                "username": "john.doe@fake.com",
                "password": "barfoo",
                "url": "https://www.example.com",
            }
        )

        domain_matches = [
            {
                "id": "345",
                "name": "example.com",
                "username": "joe.doe@fake.com",
                "password": "barfoo1",
                "url": "https://example.com",
            },
            {
                "id": "456",
                "name": "Sites/example.com",
                "username": "jane.doe@fake.com",
                "password": "foofoo2",
                "url": "http://example.com",
            }
        ]

        fqdn_response = FakeOutput.json(fqdn_matches)
        domain_response = FakeOutput.json(domain_matches)
        no_response = FakeOutput(stderr=b'Error: Could not find specified account(s).')
        dmenu_response = FakeOutput(
            stdout=b'23456 | Sites/www.example.com | https://www.example.com | john.doe@fake.com')

        # lpass command will return results for search against
        # www.example.com, example.com, but not wwwexample.com and its ipv4
        subprocess_mock.side_effect = [fqdn_response, domain_response,
                                       no_response, no_response,
                                       dmenu_response]

        arguments_mock.url = fqdn_matches[0]['url']
        arguments_mock.merge_candidates = True
        exit_code = qute_lastpass.main(arguments_mock)

        assert exit_code == qute_lastpass.ExitCodes.SUCCESS

        subprocess_mock.assert_has_calls([
            call(['lpass', 'show', '-x', '-j', '-G', '\\bwww\\.example\\.com'],
                 stdout=ANY, stderr=ANY),
            call(['lpass', 'show', '-x', '-j', '-G', '\\bexample\\.com'],
                 stdout=ANY, stderr=ANY),
            call(['lpass', 'show', '-x', '-j', '-G', '\\bwwwexample'],
                 stdout=ANY, stderr=ANY),
            call(['lpass', 'show', '-x', '-j', '-G', '\\bexample'],
                 stdout=ANY, stderr=ANY),
            call(['rofi', '-dmenu'],
                 input=b'12345 | www.example.com | https://www.example.com | fake@fake.com\n23456 | Sites/www.example.com | https://www.example.com | john.doe@fake.com\n345 | example.com | https://example.com | joe.doe@fake.com\n456 | Sites/example.com | http://example.com | jane.doe@fake.com',
                 stdout=ANY)
        ])

        qutecommand_mock.assert_has_calls([
            call(
                'fake-key \\j\\o\\h\\n\\.\\d\\o\\e\\@\\f\\a\\k\\e\\.\\c\\o\\m'),
            call('fake-key <Tab>'),
            call('fake-key \\b\\a\\r\\f\\o\\o'),
            call('mode-enter insert')
        ])
