# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Steps for bdd-like tests."""

import re
import time
import json
import logging

import yaml
import pytest_bdd as bdd

from helpers import utils  # pylint: disable=import-error


@bdd.given(bdd.parsers.parse("I set {sect} -> {opt} to {value}"))
def set_setting(quteproc, sect, opt, value):
    quteproc.set_setting(sect, opt, value)


@bdd.given(bdd.parsers.parse("I open {path}"))
def open_path_given(quteproc, path):
    quteproc.open_path(path, new_tab=True)


@bdd.when(bdd.parsers.parse("I open {path}"))
def open_path_when(quteproc, path):
    quteproc.open_path(path)


@bdd.when(bdd.parsers.parse("I set {sect} -> {opt} to {value}"))
def set_setting_when(quteproc, sect, opt, value):
    quteproc.set_setting(sect, opt, value)


@bdd.given(bdd.parsers.parse("I run {command}"))
def run_command_given(quteproc, command):
    quteproc.send_cmd(command)


@bdd.given("I have a fresh instance")
def fresh_instance(quteproc):
    """Restart qutebrowser instance for tests needing a fresh state."""
    quteproc.terminate()
    quteproc.start()


@bdd.when(bdd.parsers.parse("I run {command}"))
def run_command_when(quteproc, httpbin, command):
    if 'with count' in command:
        command, count = command.split(' with count ')
        count = int(count)
    else:
        count = None
    command = command.replace('(port)', str(httpbin.port))
    quteproc.send_cmd(command, count=count)


@bdd.when(bdd.parsers.parse("I reload"))
def reload(qtbot, httpbin, quteproc, command):
    with qtbot.waitSignal(httpbin.new_request, raising=True):
        quteproc.send_cmd(':reload')


@bdd.when(bdd.parsers.parse("I wait until {path} is loaded"))
def wait_until_loaded(quteproc, path):
    quteproc.wait_for_load_finished(path)


@bdd.when(bdd.parsers.re(r'I wait for (?P<is_regex>regex )?"'
                         r'(?P<pattern>[^"]+)" in the log'))
def wait_in_log(quteproc, is_regex, pattern):
    if is_regex:
        pattern = re.compile(pattern)
    quteproc.wait_for(message=pattern)


@bdd.when(bdd.parsers.re(r'I wait for the (?P<category>error|message|warning) '
                         r'"(?P<message>.*)"'))
def wait_for_message(quteproc, httpbin, category, message):
    expect_error(quteproc, httpbin, category, message)


@bdd.then(bdd.parsers.parse("{path} should be loaded"))
def path_should_be_loaded(httpbin, path):
    httpbin.wait_for(verb='GET', path='/' + path)


@bdd.then(bdd.parsers.parse("The requests should be:\n{pages}"))
def list_of_loaded_pages(httpbin, pages):
    expected_requests = [httpbin.ExpectedRequest('GET', '/' + path.strip())
                         for path in pages.split('\n')]
    actual_requests = httpbin.get_requests()
    assert actual_requests == expected_requests


@bdd.then(bdd.parsers.re(r'the (?P<category>error|message|warning) '
                         r'"(?P<message>.*)" should be shown.'))
def expect_error(quteproc, httpbin, category, message):
    category_to_loglevel = {
        'message': logging.INFO,
        'error': logging.ERROR,
        'warning': logging.WARNING,
    }
    message = message.replace('(port)', str(httpbin.port))
    quteproc.mark_expected(category='message',
                           loglevel=category_to_loglevel[category],
                           message=message)


@bdd.then(bdd.parsers.parse("The session should look like:\n{expected}"))
def compare_session(quteproc, expected):
    # Translate ... to ellipsis in YAML.
    loader = yaml.SafeLoader(expected)
    loader.add_constructor('!ellipsis', lambda loader, node: ...)
    loader.add_implicit_resolver('!ellipsis', re.compile(r'\.\.\.'), None)

    data = quteproc.get_session()
    expected = loader.get_data()
    assert utils.partial_compare(data, expected)


@bdd.when(bdd.parsers.parse("I wait {delay}s"))
def wait_time(quteproc, delay):
    time.sleep(float(delay))


@bdd.then(bdd.parsers.parse('"{pattern}" should not be logged'))
def ensure_not_logged(quteproc, pattern):
    quteproc.ensure_not_logged(message=pattern)


@bdd.then(bdd.parsers.parse('the javascript message "{message}" should be '
                            'logged'))
def javascript_message_logged(quteproc, message):
    quteproc.wait_for(category='js', function='javaScriptConsoleMessage',
                      message='[*] {}'.format(message))


@bdd.then("no crash should happen")
def no_crash():
    """Don't do anything.

    This is actually a NOP as a crash is already checked in the log."""
    pass


@bdd.then(bdd.parsers.parse("the header {header} should be set to {value}"))
def check_header(quteproc, header, value):
    """Check if a given header is set correctly.

    This assumes we're on the httpbin header page.
    """
    content = quteproc.get_content()
    data = json.loads(content)
    print(data)
    assert data['headers'][header] == value
