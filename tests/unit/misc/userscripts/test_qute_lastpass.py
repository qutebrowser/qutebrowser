# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for misc.userscripts.qute-lastpass."""

import subprocess
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec

from unittest.mock import MagicMock, call
import pytest
import json

# qute-lastpass violates naming convention and does not have .py extension
spec = spec_from_loader("qute_lastpass", SourceFileLoader("qute_lastpass",
                                                          "../../../../misc/userscripts/qute-lastpass"))
qute_lastpass = module_from_spec(spec)
spec.loader.exec_module(qute_lastpass)

default_lpass_match = [
    {
        "id": "12345",
        "name": "www.example.com",
        "username": "fake@fake.com",
        "password": "foobar",
        "url": "https://www.example.com",
    }
]


def get_response_mock(stdout='', stderr=''):
    response = MagicMock()
    response.stdout = stdout.encode()
    response.stderr = stderr.encode()

    return response


def setup_subprocess_mock(mocker, stdout='', stderr=''):
    mocker.patch('subprocess.run')

    subprocess.run.return_value = get_response_mock(stdout, stderr)


# Default arguments passed to qute-lastpass
def get_arguments_mock(url):
    arguments = MagicMock()
    arguments.url = url
    arguments.dmenu_invocation = 'rofi -dmenu'
    arguments.insert_mode = True
    arguments.io_encoding = 'UTF-8'
    arguments.merge_candidates = False
    arguments.password_only = False
    arguments.username_only = False

    return arguments


class TestQuteLastPassComponents:
    """Test qute-lastpass components"""

    def test_fake_key_raw(self):
        """Test if fake_key_raw properly escapes characters being sent into qutebrowser"""
        qute_lastpass.qute_command = MagicMock()

        qute_lastpass.fake_key_raw('john.doe@example.com ')

        qute_lastpass.qute_command.assert_called_once_with(
            'fake-key \\j\\o\\h\\n\\.\\d\\o\\e\\@\\e\\x\\a\\m\\p\\l\\e\\.\\c\\o\\m" "')

    def test_dmenu(self, mocker):
        """Test if dmenu command receives properly formatted lpass entries"""

        entries = [
            "1234 | example.com | https://www.example.com | john.doe@example.com",
            "2345 | example2.com | https://www.example2.com | jane.doe@example.com",
        ]

        setup_subprocess_mock(mocker, entries[1])

        selected = qute_lastpass.dmenu(entries, 'rofi -dmenu', 'UTF-8')

        subprocess.run.assert_called_once_with(
            ['rofi', '-dmenu'],
            input='\n'.join(entries).encode(),
            stdout=mocker.ANY)

        assert selected == entries[1]

    def test_pass_subprocess_args(self, mocker):
        """Test if pass_ calls subprocess with correct arguments"""
        setup_subprocess_mock(mocker, '[{}]')

        qute_lastpass.pass_('example.com', 'utf-8')

        subprocess.run.assert_called_once_with(
            ['lpass', 'show', '-x', '-j', '-G', '\\bexample\\.com'],
            stdout=mocker.ANY, stderr=mocker.ANY)

    def test_pass_returns_candidates(self, mocker):
        """Test if pass_ returns expected lpass site entry"""

        setup_subprocess_mock(mocker, json.dumps(default_lpass_match))

        response = qute_lastpass.pass_('www.example.com', 'utf-8')
        assert response[1] == ''

        candidates = response[0]

        assert len(candidates) == 1
        assert candidates[0] == default_lpass_match[0]

    def test_pass_no_accounts(self, mocker):
        """Test if pass_ handles no accounts as an empty lpass result"""

        error_message = 'Error: Could not find specified account(s).'
        setup_subprocess_mock(mocker, stderr=error_message)

        response = qute_lastpass.pass_('www.example.com', 'utf-8')
        assert response[0] == []
        assert response[1] == ''

    def test_pass_returns_error(self, mocker):
        """Test if pass_ returns error from lpass"""

        error_message = 'Error: Could not find decryption key. Perhaps you need to login with `lpass login`.'
        setup_subprocess_mock(mocker, stderr=error_message)

        response = qute_lastpass.pass_('www.example.com', 'utf-8')
        assert response[0] == []
        assert response[1] == error_message


class TestQuteLastPassMain:
    """"Test qute-lastpass main"""

    def test_main_happy_path(self, mocker):
        """Test if qute-lastpass sends username/password to qutebrowser on *single* match"""

        setup_subprocess_mock(mocker, json.dumps(default_lpass_match))
        qute_lastpass.qute_command = MagicMock()

        arguments = get_arguments_mock(default_lpass_match[0]['url'])
        exit_code = qute_lastpass.main(arguments)

        assert exit_code == qute_lastpass.ExitCodes.SUCCESS

        qute_lastpass.qute_command.assert_has_calls([
            call('fake-key \\f\\a\\k\\e\\@\\f\\a\\k\\e\\.\\c\\o\\m'),
            call('fake-key <Tab>'),
            call('fake-key \\f\\o\\o\\b\\a\\r'),
            call('enter-mode insert')
        ])

    def test_main_no_candidates(self, mocker):
        """Test if qute-lastpass returns correct exit code and message when no entries are found"""

        error_message = 'Error: Could not find specified account(s).'
        setup_subprocess_mock(mocker, stderr=error_message)

        qute_lastpass.stderr = MagicMock()
        qute_lastpass.qute_command = MagicMock()

        arguments = get_arguments_mock(default_lpass_match[0]['url'])
        exit_code = qute_lastpass.main(arguments)

        assert exit_code == qute_lastpass.ExitCodes.NO_PASS_CANDIDATES
        qute_lastpass.stderr.assert_called_with(
            "No pass candidates for URL 'https://www.example.com' found!")
        qute_lastpass.qute_command.assert_not_called()

    def test_main_lpass_failure(self, mocker):
        """Test if qute-lastpass returns correct exit code and message when lpass experiences failure"""

        error_message = 'Error: Could not find decryption key. Perhaps you need to login with `lpass login`.'
        setup_subprocess_mock(mocker, stderr=error_message)

        qute_lastpass.stderr = MagicMock()
        qute_lastpass.qute_command = MagicMock()

        arguments = get_arguments_mock(default_lpass_match[0]['url'])
        exit_code = qute_lastpass.main(arguments)

        assert exit_code == qute_lastpass.ExitCodes.FAILURE
        qute_lastpass.stderr.assert_called_with(
            "LastPass CLI returned for www.example.com - Error: Could not find decryption key. Perhaps you need to login with `lpass login`.")
        qute_lastpass.qute_command.assert_not_called()

    def test_main_username_only_flag(self, mocker):
        """Test if --username-only flag sends username only"""

        setup_subprocess_mock(mocker, json.dumps(default_lpass_match))
        qute_lastpass.qute_command = MagicMock()

        arguments = get_arguments_mock(default_lpass_match[0]['url'])
        arguments.username_only = True
        qute_lastpass.main(arguments)

        qute_lastpass.qute_command.assert_has_calls([
            call('fake-key \\f\\a\\k\\e\\@\\f\\a\\k\\e\\.\\c\\o\\m'),
            call('enter-mode insert')
        ])

    def test_main_password_only_flag(self, mocker):
        """Test if --password-only flag sends password only"""

        setup_subprocess_mock(mocker, json.dumps(default_lpass_match))
        qute_lastpass.qute_command = MagicMock()

        arguments = get_arguments_mock(default_lpass_match[0]['url'])
        arguments.password_only = True
        qute_lastpass.main(arguments)

        qute_lastpass.qute_command.assert_has_calls([
            call('fake-key \\f\\o\\o\\b\\a\\r'),
            call('enter-mode insert')
        ])

    def test_main_multiple_candidates(self, mocker):
        """Test if qute-lastpass uses dmenu-invocation when lpass returns multiple candidates"""

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

        mocker.patch('subprocess.run')

        lpass_response = get_response_mock(json.dumps(multiple_matches))
        dmenu_response = get_response_mock(
            '23456 | Sites/www.example.com | https://www.example.com | john.doe@fake.com')

        subprocess.run.side_effect = [lpass_response, dmenu_response]
        qute_lastpass.qute_command = MagicMock()

        arguments = get_arguments_mock(multiple_matches[0]['url'])
        exit_code = qute_lastpass.main(arguments)

        assert exit_code == qute_lastpass.ExitCodes.SUCCESS

        subprocess.run.assert_has_calls([
            call(['lpass', 'show', '-x', '-j', '-G', '\\bwww\\.example\\.com'],
                 stdout=mocker.ANY, stderr=mocker.ANY),
            call(['rofi', '-dmenu'],
                 input=b'12345 | www.example.com | https://www.example.com | fake@fake.com\n23456 | Sites/www.example.com | https://www.example.com | john.doe@fake.com',
                 stdout=mocker.ANY)
        ])

        qute_lastpass.qute_command.assert_has_calls([
            call(
                'fake-key \\j\\o\\h\\n\\.\\d\\o\\e\\@\\f\\a\\k\\e\\.\\c\\o\\m'),
            call('fake-key <Tab>'),
            call('fake-key \\b\\a\\r\\f\\o\\o'),
            call('enter-mode insert')
        ])

    def test_main_merge_candidates(self, mocker):
        """Test if qute-lastpass properly merges multiple responses from lpass"""

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

        mocker.patch('subprocess.run')

        fqdn_response = get_response_mock(json.dumps(fqdn_matches))
        domain_response = get_response_mock(json.dumps(domain_matches))
        no_response = get_response_mock(
            stderr='Error: Could not find specified account(s).')
        dmenu_response = get_response_mock(
            '23456 | Sites/www.example.com | https://www.example.com | john.doe@fake.com')

        ## lpass command will return results for search against www.example.com, example.com, but not wwwexample.com and its ipv4
        subprocess.run.side_effect = [fqdn_response, domain_response,
                                      no_response, no_response,
                                      dmenu_response]
        qute_lastpass.qute_command = MagicMock()

        arguments = get_arguments_mock(fqdn_matches[0]['url'])
        arguments.merge_candidates = True
        exit_code = qute_lastpass.main(arguments)

        assert exit_code == qute_lastpass.ExitCodes.SUCCESS

        subprocess.run.assert_has_calls([
            call(['lpass', 'show', '-x', '-j', '-G', '\\bwww\\.example\\.com'],
                 stdout=mocker.ANY, stderr=mocker.ANY),
            call(['lpass', 'show', '-x', '-j', '-G', '\\bexample\\.com'],
                 stdout=mocker.ANY, stderr=mocker.ANY),
            call(['lpass', 'show', '-x', '-j', '-G', '\\bwwwexample'],
                 stdout=mocker.ANY, stderr=mocker.ANY),
            call(['lpass', 'show', '-x', '-j', '-G', '\\bexample'],
                 stdout=mocker.ANY, stderr=mocker.ANY),
            call(['rofi', '-dmenu'],
                 input=b'12345 | www.example.com | https://www.example.com | fake@fake.com\n23456 | Sites/www.example.com | https://www.example.com | john.doe@fake.com\n345 | example.com | https://example.com | joe.doe@fake.com\n456 | Sites/example.com | http://example.com | jane.doe@fake.com',
                 stdout=mocker.ANY)
        ])

        qute_lastpass.qute_command.assert_has_calls([
            call(
                'fake-key \\j\\o\\h\\n\\.\\d\\o\\e\\@\\f\\a\\k\\e\\.\\c\\o\\m'),
            call('fake-key <Tab>'),
            call('fake-key \\b\\a\\r\\f\\o\\o'),
            call('enter-mode insert')
        ])
