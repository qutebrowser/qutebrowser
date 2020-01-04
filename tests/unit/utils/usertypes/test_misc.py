# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


from qutebrowser.utils import usertypes


def test_abstract_certificate_error_wrapper():
    err = object()
    wrapper = usertypes.AbstractCertificateErrorWrapper(err)
    assert wrapper._error is err


def test_unset_object_identity():
    assert usertypes.Unset() is not usertypes.Unset()
    assert usertypes.UNSET is usertypes.UNSET


def test_unset_object_repr():
    assert repr(usertypes.UNSET) == '<UNSET>'
