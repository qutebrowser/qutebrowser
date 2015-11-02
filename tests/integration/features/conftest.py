import logging

import pytest_bdd as bdd


@bdd.given(bdd.parsers.parse("I set {sect} -> {opt} to {value}"))
def set_setting(quteproc, sect, opt, value):
    quteproc.set_setting(sect, opt, value)


@bdd.given(bdd.parsers.parse("I open {path}"))
def open_path(quteproc, path):
    quteproc.open_path(path, new_tab=True)


@bdd.when(bdd.parsers.parse("I open {path}"))
def open_path_when(quteproc, path):
    quteproc.open_path(path)


@bdd.when(bdd.parsers.parse("I run {command}"))
def run_command(quteproc, command):
    quteproc.send_cmd(command)


@bdd.when(bdd.parsers.parse("I reload"))
def reload(qtbot, httpbin, quteproc, command):
    with qtbot.waitSignal(httpbin.new_request, raising=True):
        quteproc.send_cmd(':reload')


@bdd.then(bdd.parsers.parse("{path} should be loaded"))
def path_should_be_loaded(httpbin, path):
    requests = httpbin.get_requests()
    assert requests[-1] == httpbin.Request('GET', '/' + path)


@bdd.then(bdd.parsers.parse("The requests should be:\n{pages}"))
def list_of_loaded_pages(httpbin, pages):
    requests = [httpbin.Request('GET', '/' + path.strip())
                for path in pages.split('\n')]
    assert httpbin.get_requests() == requests


@bdd.then(bdd.parsers.re(r'the (?P<category>error|message) "(?P<message>.*)" '
                         r'should be shown.'))
def expect_error(quteproc, httpbin, category, message):
    category_to_loglevel = {
        'message': logging.INFO,
        'error': logging.ERROR,
    }
    message = message.replace('(port)', str(httpbin.port))
    quteproc.mark_expected(category='message',
                           loglevel=category_to_loglevel[category],
                           message=message)
