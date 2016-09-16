# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Global instances of the completion models."""

from qutebrowser.utils import usertypes
from qutebrowser.completion.models import miscmodels, urlmodel, configmodel


def get(completion):
    """Get a certain completion. Initializes the completion if needed."""
    if completion == usertypes.Completion.command:
        return miscmodels.command
    if completion == usertypes.Completion.helptopic:
        return miscmodels.helptopic
    if completion == usertypes.Completion.tab:
        return miscmodels.buffer
    if completion == usertypes.Completion.quickmark_by_name:
        return miscmodels.quickmark
    if completion == usertypes.Completion.bookmark_by_url:
        return miscmodels.bookmark
    if completion == usertypes.Completion.sessions:
        return miscmodels.session
    if completion == usertypes.Completion.bind:
        return miscmodels.bind
    if completion == usertypes.Completion.section:
        return configmodel.section
    if completion == usertypes.Completion.option:
        return configmodel.option
    if completion == usertypes.Completion.value:
        return configmodel.value
    if completion == usertypes.Completion.url:
        return urlmodel.url


def init():
    pass
