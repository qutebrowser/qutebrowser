# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Various global objects."""

# NOTE: We need to be careful with imports here, as this is imported from
# earlyinit.

import argparse
from typing import TYPE_CHECKING, Any, Dict, Set, Union, cast

if TYPE_CHECKING:
    from qutebrowser import app
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
qapp = cast('app.Application', None)
