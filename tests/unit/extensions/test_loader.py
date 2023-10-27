# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import types

import pytest

from qutebrowser.extensions import loader
from qutebrowser.misc import objects


pytestmark = pytest.mark.usefixtures('data_tmpdir', 'config_tmpdir',
                                     'fake_args')


def test_on_walk_error():
    with pytest.raises(ImportError, match='Failed to import foo'):
        loader._on_walk_error('foo')


def test_walk_normal():
    names = [info.name for info in loader._walk_normal()]
    assert 'qutebrowser.components.scrollcommands' in names


def test_walk_pyinstaller():
    # We can't test whether we get something back without being frozen by
    # PyInstaller, but at least we can test that we don't crash.
    list(loader._walk_pyinstaller())


def test_load_component(monkeypatch):
    monkeypatch.setattr(objects, 'commands', {})

    info = loader.ExtensionInfo(name='qutebrowser.components.scrollcommands')
    mod = loader._load_component(info, skip_hooks=True)

    assert hasattr(mod, 'scroll_to_perc')
    assert 'scroll-to-perc' in objects.commands


@pytest.fixture
def module(monkeypatch, request):
    mod = types.ModuleType('testmodule')

    monkeypatch.setattr(loader, '_module_infos', [])
    monkeypatch.setattr(loader.importlib, 'import_module',
                        lambda _name: mod)

    mod.info = loader.add_module_info(mod)
    return mod


def test_get_init_context(data_tmpdir, config_tmpdir, fake_args):
    ctx = loader._get_init_context()
    assert str(ctx.data_dir) == data_tmpdir
    assert str(ctx.config_dir) == config_tmpdir
    assert ctx.args == fake_args


def test_add_module_info():
    # pylint: disable=no-member
    mod = types.ModuleType('testmodule')
    info1 = loader.add_module_info(mod)
    assert mod.__qute_module_info is info1
    assert mod.__qute_module_info.module is mod

    info2 = loader.add_module_info(mod)
    assert mod.__qute_module_info is info1
    assert info2 is info1


class _Hook:

    """Hook to use in tests."""

    __name__ = '_Hook'

    def __init__(self):
        self.called = False
        self.raising = False

    def __call__(self, *args):
        if self.raising:
            raise AssertionError("Should not be called!")
        self.called = True


@pytest.fixture
def hook():
    return _Hook()


def test_skip_hooks(hook, module):
    hook.raising = True

    module.info.init_hook = hook
    module.info.config_changed_hooks = [(None, hook)]

    info = loader.ExtensionInfo(name='testmodule')
    loader._load_component(info, skip_hooks=True)
    loader._on_config_changed('test')

    assert not hook.called


@pytest.mark.parametrize('option_filter, option, called', [
    (None, 'content.javascript.enabled', True),
    ('content.javascript', 'content.javascript.enabled', True),
    ('content.javascript.enabled', 'content.javascript.enabled', True),
    ('content.javascript.log', 'content.javascript.enabled', False),
])
def test_on_config_changed(configdata_init, hook, module,
                           option_filter, option, called):
    module.info.config_changed_hooks = [(option_filter, hook)]

    info = loader.ExtensionInfo(name='testmodule')
    loader._load_component(info)
    loader._on_config_changed(option)

    assert hook.called == called


def test_init_hook(hook, module):
    module.info.init_hook = hook
    info = loader.ExtensionInfo(name='testmodule')
    loader._load_component(info)
    assert hook.called
