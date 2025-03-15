# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Models for the command completion."""

from typing import Optional
from collections.abc import Sequence
from qutebrowser.completion.models.util import DeleteFuncType
from qutebrowser.qt.core import QAbstractItemModel


class BaseCategory(QAbstractItemModel):
    """Abstract base class for categories of CompletionModels.

    Extends QAbstractItemModel with a few attributes we expect to be present.

    TODO: actually enforce that child classes set these variables, either via
    mypy (how) or turning these variables into abstract properties, eg https://stackoverflow.com/a/50381071
    """

    name: str
    columns_to_filter: Sequence[int]
    delete_func: Optional[DeleteFuncType] = None
