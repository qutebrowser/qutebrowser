# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Various global objects."""

# NOTE: We need to be careful with imports here, as this is imported from
# earlyinit.

import argparse
from typing import TYPE_CHECKING, Any, Dict, Set, Union, cast

if TYPE_CHECKING:
    from PyQt5.QtWidgets import QApplication
    from qutebrowser.utils import usertypes
    from qutebrowser.commands import command


class NoBackend:

    """Special object when there's no backend set so we notice that."""

    @property
    def name(self) -> str:
        raise AssertionError("No backend set!")

    def __eq__(self, other: Any) -> bool:
        raise AssertionError("No backend set!")


backend: Union['usertypes.Backend', NoBackend] = NoBackend()
commands: Dict[str, 'command.Command'] = {}
debug_flags: Set[str] = set()
args = cast(argparse.Namespace, None)
qapp = cast('QApplication', None)
