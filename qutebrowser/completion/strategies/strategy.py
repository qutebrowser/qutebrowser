# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Classes that return miscellaneous completion models."""

from typing import Sequence, Optional
from abc import ABC, abstractmethod

from qutebrowser.completion import completionmodel
from qutebrowser.completion.completer import CompletionInfo


class DeletionUnsupportedError(Exception):
    """Raises when the completion strategy does not support deletion"""


class CompletionStrategy(ABC):
    COLUMN_WIDTHS = (20, 70, 10)

    def __init__(self):
        self.model = completionmodel.CompletionModel(column_widths=self.COLUMN_WIDTHS)

    @abstractmethod
    def populate(self, *args: str, info: Optional[CompletionInfo]) -> None:
        pass

    @classmethod
    def delete(cls, data: Sequence[str]) -> None:
        raise DeletionUnsupportedError(f"{cls} does not support deletion")
