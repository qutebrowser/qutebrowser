# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest_bdd as bdd
bdd.scenarios('zoom.feature')


@bdd.then(bdd.parsers.parse("the zoom should be {zoom}%"))
def check_zoom(quteproc, zoom):
    data = quteproc.get_session()
    histories = data['windows'][0]['tabs'][0]['history']
    value = next(h for h in histories if 'zoom' in h)['zoom'] * 100
    assert abs(value - float(zoom)) < 0.0001
