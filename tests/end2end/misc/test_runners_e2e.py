# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019-2020 Jay Kamat <jaygkamat@gmail.com>
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

"""Tests for runners."""

import logging

import pytest


def command_expansion_base(
        quteproc, send_msg, recv_msg, url="data/hello.txt"):
    quteproc.open_path(url)
    quteproc.send_cmd(':message-info ' + send_msg)

    quteproc.mark_expected(category='message',
                           loglevel=logging.INFO,
                           message=recv_msg)


@pytest.mark.parametrize('send_msg, recv_msg', [
    # escaping by double-quoting
    ('foo{{url}}bar', 'foo{url}bar'),

    ('foo{url}', 'foohttp://localhost:*/hello.txt'),
    ('foo{url:pretty}', 'foohttp://localhost:*/hello.txt'),
    ('foo{url:domain}', 'foohttp://localhost:*'),
    # test {url:auth} on a site with no auth
    ('foo{url:auth}', 'foo'),
    ('foo{url:scheme}', 'foohttp'),
    ('foo{url:host}', 'foolocalhost'),
    ('foo{url:path}', 'foo*/hello.txt'),
])
def test_command_expansion(quteproc, send_msg, recv_msg):
    command_expansion_base(quteproc, send_msg, recv_msg)


@pytest.mark.parametrize('send_msg, recv_msg, url', [
    ('foo{title}', 'fooTest title', 'data/title.html'),
    ('foo{url:query}', 'fooq=bar', 'data/hello.txt?q=bar'),

    # multiple variable expansion
    ('{title}bar{url}', 'Test titlebarhttp://localhost:*/title.html', 'data/title.html'),
])
def test_command_expansion_complex(
        quteproc, send_msg, recv_msg, url):
    command_expansion_base(quteproc, send_msg, recv_msg, url)


def test_command_expansion_basic_auth(quteproc, server):
    url = ('http://user1:password1@localhost:{port}/basic-auth/user1/password1'
           .format(port=server.port))
    quteproc.open_url(url)
    quteproc.send_cmd(':message-info foo{url:auth}')

    quteproc.mark_expected(
        category='message',
        loglevel=logging.INFO, message='foouser1:password1@')


def test_command_expansion_clipboard(quteproc):
    quteproc.send_cmd(':debug-set-fake-clipboard "foo"')
    command_expansion_base(
        quteproc, '{clipboard}bar{url}',
        "foobarhttp://localhost:*/hello.txt")
    quteproc.send_cmd(':debug-set-fake-clipboard "{{url}}"')
    command_expansion_base(
        quteproc, '{clipboard}bar{url}',
        "{url}barhttp://localhost:*/hello.txt")
