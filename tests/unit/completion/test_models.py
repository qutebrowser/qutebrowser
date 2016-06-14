# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Tests for completion models."""

import collections

from qutebrowser.completion.models import miscmodels


def test_command_completion(monkeypatch, stubs, config_stub, key_config_stub):
    """Test the results of command completion.

    Validates that:
        - only non-hidden and non-deprecated commands are included
        - commands are sorted by name
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
    """
    _patch_cmdutils(monkeypatch, stubs,
                    'qutebrowser.completion.models.miscmodels.cmdutils')
    config_stub.data['aliases'] = {'rock': 'roll'}
    key_config_stub.set_bindings_for('normal', {'s': 'stop', 'rr': 'roll'})
    actual = _get_completions(miscmodels.CommandCompletionModel())
    assert actual == [
        ("Commands", [
            ('drop', 'drop all user data', ''),
            ('rock', "Alias for 'roll'", ''),
            ('roll', 'never gonna give you up', 'rr'),
            ('stop', 'stop qutebrowser', 's')
        ])
    ]


def test_help_completion(monkeypatch, stubs):
    """Test the results of command completion.

    Validates that:
        - only non-hidden and non-deprecated commands are included
        - commands are sorted by name
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
        - only the first line of a multiline description is shown
    """
    module = 'qutebrowser.completion.models.miscmodels'
    _patch_cmdutils(monkeypatch, stubs, module + '.cmdutils')
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    actual = _get_completions(miscmodels.HelpCompletionModel())
    assert actual == [
        ("Commands", [
            (':drop', 'drop all user data', ''),
            (':roll', 'never gonna give you up', ''),
            (':stop', 'stop qutebrowser', '')
        ]),
        ("Settings", [
            ('general->time', 'Is an illusion.', ''),
            ('general->volume', 'Goes to 11', ''),
            ('ui->gesture', 'Waggle your hands to control qutebrowser', ''),
            ('ui->mind', 'Enable mind-control ui (experimental)', ''),
            ('ui->voice', 'Whether to respond to voice commands', ''),
        ])
    ]


def _get_completions(model):
    """Collect all the completion entries of a model, organized by category.

    The result is a list of form:
    [
        (CategoryName: [(name, desc, misc), ...]),
        (CategoryName: [(name, desc, misc), ...]),
        ...
    ]
    """
    completions = []
    for i in range(0, model.rowCount()):
        category = model.item(i)
        entries = []
        for j in range(0, category.rowCount()):
            name = category.child(j, 0)
            desc = category.child(j, 1)
            misc = category.child(j, 2)
            entries.append((name.text(), desc.text(), misc.text()))
        completions.append((category.text(), entries))
    return completions


def _patch_cmdutils(monkeypatch, stubs, symbol):
    """Patch the cmdutils module to provide fake commands."""
    cmd_utils = stubs.FakeCmdUtils({
        'stop': stubs.FakeCommand(name='stop', desc='stop qutebrowser'),
        'drop': stubs.FakeCommand(name='drop', desc='drop all user data'),
        'roll': stubs.FakeCommand(name='roll', desc='never gonna give you up'),
        'hide': stubs.FakeCommand(name='hide', hide=True),
        'depr': stubs.FakeCommand(name='depr', deprecated=True),
    })
    monkeypatch.setattr(symbol, cmd_utils)


def _patch_configdata(monkeypatch, stubs, symbol):
    """Patch the configdata module to provide fake data."""
    data = collections.OrderedDict([
        ('general', stubs.FakeConfigSection(
            ('time', 'Is an illusion.\n\nLunchtime doubly so.'),
            ('volume', 'Goes to 11'))),
        ('ui', stubs.FakeConfigSection(
            ('gesture', 'Waggle your hands to control qutebrowser'),
            ('mind', 'Enable mind-control ui (experimental)'),
            ('voice', 'Whether to respond to voice commands'))),
    ])
    monkeypatch.setattr(symbol, data)
