# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Global instances of the completion models.

Module attributes:
    _instances: An dict of available completions.
    INITIALIZERS: A {usertypes.Completion: callable} dict of functions to
                  initialize completions.
"""

import functools

from PyQt5.QtCore import pyqtSlot, Qt

from qutebrowser.completion.models import miscmodels, urlmodel, configmodel
from qutebrowser.completion.models.sortfilter import CompletionFilterModel
from qutebrowser.utils import objreg, usertypes, log, debug
from qutebrowser.config import configdata


_instances = {}


def _init_model(klass, *args, dumb_sort=None, **kwargs):
    """Helper to initialize a model.

    Args:
        klass: The class of the model to initialize.
        *args: Arguments to pass to the model.
        **kwargs: Keyword arguments to pass to the model.
        dumb_sort: Passed to CompletionFilterModel.
    """
    app = objreg.get('app')
    return CompletionFilterModel(klass(*args, parent=app, **kwargs),
                                 dumb_sort=dumb_sort, parent=app)


def _init_command_completion():
    """Initialize the command completion model."""
    log.completion.debug("Initializing command completion.")
    model = _init_model(miscmodels.CommandCompletionModel)
    _instances[usertypes.Completion.command] = model


def _init_helptopic_completion():
    """Initialize the helptopic completion model."""
    log.completion.debug("Initializing helptopic completion.")
    model = _init_model(miscmodels.HelpCompletionModel)
    _instances[usertypes.Completion.helptopic] = model


def _init_url_completion():
    """Initialize the URL completion model."""
    log.completion.debug("Initializing URL completion.")
    with debug.log_time(log.completion, 'URL completion init'):
        model = _init_model(urlmodel.UrlCompletionModel,
                            dumb_sort=Qt.DescendingOrder)
        _instances[usertypes.Completion.url] = model


def _init_setting_completions():
    """Initialize setting completion models."""
    log.completion.debug("Initializing setting completion.")
    _instances[usertypes.Completion.section] = _init_model(
        configmodel.SettingSectionCompletionModel)
    _instances[usertypes.Completion.option] = {}
    _instances[usertypes.Completion.value] = {}
    for sectname in configdata.DATA:
        model = _init_model(configmodel.SettingOptionCompletionModel, sectname)
        _instances[usertypes.Completion.option][sectname] = model
        _instances[usertypes.Completion.value][sectname] = {}
        for opt in configdata.DATA[sectname].keys():
            model = _init_model(configmodel.SettingValueCompletionModel,
                                sectname, opt)
            _instances[usertypes.Completion.value][sectname][opt] = model


@pyqtSlot()
def init_quickmark_completions():
    """Initialize quickmark completion models."""
    log.completion.debug("Initializing quickmark completion.")
    try:
        _instances[usertypes.Completion.quickmark_by_url].deleteLater()
        _instances[usertypes.Completion.quickmark_by_name].deleteLater()
    except KeyError:
        pass
    model = _init_model(miscmodels.QuickmarkCompletionModel, 'url')
    _instances[usertypes.Completion.quickmark_by_url] = model
    model = _init_model(miscmodels.QuickmarkCompletionModel, 'name')
    _instances[usertypes.Completion.quickmark_by_name] = model


@pyqtSlot()
def init_session_completion():
    """Initialize session completion model."""
    log.completion.debug("Initializing session completion.")
    try:
        _instances[usertypes.Completion.sessions].deleteLater()
    except KeyError:
        pass
    model = _init_model(miscmodels.SessionCompletionModel)
    _instances[usertypes.Completion.sessions] = model


INITIALIZERS = {
    usertypes.Completion.command: _init_command_completion,
    usertypes.Completion.helptopic: _init_helptopic_completion,
    usertypes.Completion.url: _init_url_completion,
    usertypes.Completion.section: _init_setting_completions,
    usertypes.Completion.option: _init_setting_completions,
    usertypes.Completion.value: _init_setting_completions,
    usertypes.Completion.quickmark_by_url: init_quickmark_completions,
    usertypes.Completion.quickmark_by_name: init_quickmark_completions,
    usertypes.Completion.sessions: init_session_completion,
}


def get(completion):
    """Get a certain completion. Initializes the completion if needed."""
    try:
        return _instances[completion]
    except KeyError:
        if completion in INITIALIZERS:
            INITIALIZERS[completion]()
            return _instances[completion]
        else:
            raise


def update(completions):
    """Update an already existing completion.

    Args:
        completions: An iterable of usertypes.Completions.
    """
    did_run = []
    for completion in completions:
        if completion in _instances:
            func = INITIALIZERS[completion]
            if func not in did_run:
                func()
                did_run.append(func)


def init():
    """Initialize completions. Note this only connects signals."""
    quickmark_manager = objreg.get('quickmark-manager')
    quickmark_manager.changed.connect(
        functools.partial(update, [usertypes.Completion.quickmark_by_url,
                                   usertypes.Completion.quickmark_by_name]))

    session_manager = objreg.get('session-manager')
    session_manager.update_completion.connect(
        functools.partial(update, [usertypes.Completion.sessions]))

    history = objreg.get('web-history')
    history.async_read_done.connect(
        functools.partial(update, [usertypes.Completion.url]))
