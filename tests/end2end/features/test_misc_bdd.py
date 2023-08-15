# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest_bdd as bdd
bdd.scenarios('misc.feature')


@bdd.when("I load a third-party iframe")
def load_iframe(quteproc, server, ssl_server):
    quteproc.set_setting('content.tls.certificate_errors', 'load-insecurely')
    quteproc.open_path(f'https-iframe/{ssl_server.port}', port=server.port)
    msg = quteproc.wait_for(message="Certificate error: *")
    msg.expected = True
    msg = quteproc.wait_for(message="Certificate error: *")
    msg.expected = True


@bdd.when("I turn on scroll logging")
def turn_on_scroll_logging(quteproc):
    quteproc.turn_on_scroll_logging(no_scroll_filtering=True)


@bdd.then(bdd.parsers.parse('the PDF {filename} should exist in the tmpdir'))
def pdf_exists(quteproc, tmpdir, filename):
    path = tmpdir / filename
    data = path.read_binary()
    assert data.startswith(b'%PDF')
