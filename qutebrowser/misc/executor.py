# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from threading import Event
from concurrent.futures import ThreadPoolExecutor

from qutebrowser.utils import objreg


class TaskExecutor(ThreadPoolExecutor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutting_down = Event()

    def submit(self, fn, *args, **kwargs):
        super().submit(fn, self, *args, **kwargs)

    def shutdown(self, wait=True):
        self._shutting_down.set()
        super().shutdown(wait)

    def is_shutting_down(self):
        return self._shutting_down.is_set()


def init():
    e = TaskExecutor(max_workers=2)
    objreg.register('task-executor', e)
