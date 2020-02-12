# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Various global objects."""

# NOTE: We need to be careful with imports here, as this is imported from
# earlyinit.

import typing
import argparse

if typing.TYPE_CHECKING:
    from qutebrowser.utils import usertypes
    from qutebrowser.commands import command


class NoBackend:

    """Special object when there's no backend set so we notice that."""

    @property
    def name(self) -> str:
        raise AssertionError("No backend set!")

    def __eq__(self, other: typing.Any) -> bool:
        raise AssertionError("No backend set!")


backend = NoBackend()  # type: typing.Union[usertypes.Backend, NoBackend]
commands = {}  # type: typing.Dict[str, command.Command]
debug_flags = set()  # type: typing.Set[str]
args = typing.cast(argparse.Namespace, None)
