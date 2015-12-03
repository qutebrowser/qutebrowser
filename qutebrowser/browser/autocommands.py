# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Antoni Boucher <bouanto@zoho.com>
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

"""Autocommands manager
"""

import os.path
import collections
import re

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QUrl, QObject
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication

from qutebrowser.config import config
from qutebrowser.utils import usertypes, standarddir, objreg, log, jinja
from qutebrowser.commands import runners, cmdutils, cmdexc
from qutebrowser.completion.models import instances
from qutebrowser.misc import lineparser
from qutebrowser.browser.network import qutescheme
from qutebrowser.mainwindow import mainwindow

class add_as_event:
    """Add a new method as autocmd event."""
    available_events = {}

    def __init__(self, help_text):
        self.help_text = help_text

    def __call__(self, func):
        self.available_events[func.__name__] = {'help': self.help_text, 'commands': {}, 'instance': func}


class AutocommandsManager(QObject):
    """Manage for autocommands.

    The primary key for commands is the combination between the regexp url pattern and the event type.
    """

    changed = pyqtSignal()
    available_events = {}

    def _save(self):
        """Save the autocommands to disk."""
        if self._lineparser is not None:
            self._lineparser.data = []
            for key in self.available_events.keys():
                self._lineparser.data.append('[' + key + ']')
                commands = self.available_events[key]['commands']
                for item in commands.items():
                    self._lineparser.data.append(item[0] + ' ' + item[1])
            self._lineparser.save()

    def __init__(self, parent=None):
        """Initialize and read the auto commands."""
        super().__init__(parent)

        self.available_events = add_as_event.available_events
        self.enabled = config.get('general', 'enable-autocmds')

        self._lineparser = None

        self._init_lineparser()
        self.current_section = None
        for line in self._lineparser:
            if not line.strip():
                # Ignore empty or whitespace-only lines.
                continue
            self._parse_line(line)
        self._init_savemanager(objreg.get('save-manager'))

    def register_events(self, obj):
        """Registers the events (connect the slots to the defined methods)

        Args:
            obj: The object which will emmit the signals (for the moment the webview.page() object)
        """

        methods = dir(obj)
        for key in self.available_events.keys():
            idx = methods.index(key)
            if idx >= 0:
                signal = getattr(obj, methods[idx])
                signal.connect(self.available_events[key]['instance'])

    def _init_lineparser(self):
        autocmds_directory = os.path.join(standarddir.data(), 'autocmds')
        self._lineparser = lineparser.LineParser(
            standarddir.data(), 'autocmds', parent=self)

    def _init_savemanager(self, save_manager):
        filename = os.path.join(standarddir.data(), 'autocmds')
        save_manager.add_saveable('autocmds-manager', self._save, self.changed,
                                  filename=filename)

    def _parse_line(self, line):
        pattern = "^\\[([^\\]]+)\\]$"
        if re.match(pattern, line):
            self.current_section = re.sub(pattern, "\\1", line)
        elif self.current_section != None:
            parts = line.split(maxsplit = 1)
            if (len(parts) == 2):
                self.available_events[self.current_section]['commands'][parts[0]] = parts[1]

    def run_command(self, event, parameters = {}):
        """ Runs a commands

        Args: 
            event: The event which triggered the command
            parameters: A dictionary with the arguments of the event.
        """
        page = self.sender()
        parent = page.parent()
        win_id = parent.win_id
        tab_id = parent.tab_id
        url = page.mainFrame().requestedUrl().toString()
        for url_pattern in self.available_events[event]['commands']:
            if url_pattern == '*' or re.match(url_pattern, url) != None:
                cmd = self.available_events[event]['commands'][url_pattern]
                for key in parameters.keys():
                    cmd = cmd.replace('{' + key + '}', str(parameters[key]))
                log.autocmds.debug("Executing {} because of {} for {}".format(cmd, event, url_pattern))
                # It would be nice if we could run a command in a specific tab. Like this, 
                # we would be able to run the autoevents in the tab which triggered them
                runner = runners.CommandRunner(win_id)
                runner.run_safely(cmd)


    @cmdutils.register(instance='autocmds-manager', 
            completion=[usertypes.Completion.autocommands, 
            usertypes.Completion.autocommand_events], 
            maxsplit = 2, no_cmd_split = True)
    def autocmd(self, event = None, url_pattern = None, cmd = None):
        """Adds an auto command

        Args:
            event: The browser event
            url_pattern: The url pattern for which the command will be executed
            cmd: The command to be executed
        """
        app = objreg.get('app')
        window = app.activeWindow()
        if cmd is not None and url_pattern is not None and event is not None:
            self.available_events[event]['commands'][url_pattern] = cmd
            self.__changed()
        elif url_pattern != None and event is not None:
            if url_pattern in self.available_events[event]['commands']:
                del self.available_events[event]['commands'][url_pattern]
                self.__changed()
            else:
                raise cmdexc.CommandError("No autocmd set for %s and %s" % (event, url_pattern))
        elif event != None:
            cmds = len(self.available_events[event]['commands'])
            if cmds == 0:
                raise cmdexc.CommandError("No auto command for %s" % event)
            do_del = True
            if cmds >= 2:
                q = usertypes.Question()
                q.text = 'Are you sure you want to delete \n    all commands for {} event? (Y/N)'.format(event) 
                q.mode = mode=usertypes.PromptMode.yesno
                bridge = objreg.get('message-bridge', scope='window', window=window.win_id)
                bridge.ask(q, blocking=True)
                if not q.answer:
                    do_del = False

            if do_del:
                self.available_events[event]['commands'] = {}
                self.__changed()
        else:
            tabbed_browser = objreg.get('tabbed-browser', scope='window', window=window.win_id)
            tabbed_browser.tabopen(QUrl('qute:autocmds'), background=False, explicit=True)



    def __changed(self):
        self.changed.emit()
        instances.init_autocommands_completions()


@add_as_event(help_text = '(bool ok) The page has finished loading')
@pyqtSlot(bool)
def loadFinished(ok):
    autocmds_manager = objreg.get('autocmds-manager')
    autocmds_manager.run_command('loadFinished', {'ok': str(ok)})

@add_as_event(help_text = '(void) The page started loading')
@pyqtSlot()
def loadStarted():
    autocmds_manager = objreg.get('autocmds-manager')
    autocmds_manager.run_command('loadStarted')

@add_as_event(help_text = '(string url) A link was clicked')
@pyqtSlot()
def linkClicked(url):
    autocmds_manager = objreg.get('autocmds-manager')
    autocmds_manager.run_command('linkClicked', {'url': url.toString()})

@add_as_event(help_text = '(int progress) The page loading advances')
@pyqtSlot()
def loadProgress(progress):
    autocmds_manager = objreg.get('autocmds-manager')
    autocmds_manager.run_command('loadProgress', {'progress': progress})

@add_as_event(help_text = '(string text) The status bar message')
@pyqtSlot()
def statusBarMessage(text):
    autocmds_manager = objreg.get('autocmds-manager')
    autocmds_manager.run_command('statusBarMessage', {'text': text})

@add_as_event(help_text = '(string url, string title, string textContent) A link is hovered')
@pyqtSlot()
def linkHovered(url, title, textContent):
    autocmds_manager = objreg.get('autocmds-manager')
    autocmds_manager.run_command('linkHovered', {'url': url, 'title': title, 'textContent': textContent})

@add_as_event(help_text = '(void) The selection has changed')
@pyqtSlot()
def selectionChanged():
    autocmds_manager = objreg.get('autocmds-manager')
    autocmds_manager.run_command('selectionChanged')

@add_as_event(help_text = '(string url) A download has been requested')
@pyqtSlot()
def downloadRequested(request):
    autocmds_manager = objreg.get('autocmds-manager')
    autocmds_manager.run_command('downloadRequested', {'url': request.url().toString()})

@qutescheme.add_handler('autocmds')
def autocommands_list(win_id, request):
    """Handler for qute:autocmds. View the list of auto commands"""
    autocmds_manager = objreg.get('autocmds-manager')
    autocommands = {}
    for event in autocmds_manager.available_events:
        if len(autocmds_manager.available_events[event]['commands']) > 0:
            autocommands[event] = autocmds_manager.available_events[event]
    header_text = "Available auto commands and events"
    if not autocmds_manager.enabled:
        header_text = "NOTE: The autocommands are disabled. " \
        "To enable them, set the general.enable_autocmds option " \
        "and then restart the browser"
    html = jinja.env.get_template('autocommands.html').render(
        autocommands=autocommands, header_text=header_text)
    return html.encode('UTF-8', errors='xmlcharrefreplace')

