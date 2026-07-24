# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import dataclasses
from typing import Optional


@dataclasses.dataclass
class CandidateCommand:

    """A candidate command returned from retrieval."""

    name: str
    description: str
    args: list[dict] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ResolvedCommand:

    """A resolved command from the AI provider."""

    command: str
    args: list[str] = dataclasses.field(default_factory=list)
