# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for custom pylint checkers."""


import pytest

astroid = pytest.importorskip('astroid')
pylint_testutils = pytest.importorskip('pylint.testutils')

from scripts.dev.pylint_checkers.qute_pylint.mock import (
    MockChecker,
    PatchChecker,
    is_patch_call,
    is_patch_object_call,
    is_patch_multiple_call,
    is_mock_call,
)


import_paths = (
    pytest.param('', id='import * from unittest.mock'),
    pytest.param('mock.', id='import mock from unittest'),
    pytest.param('unittest.mock.', id='import unittest.mock'),
)


@pytest.mark.parametrize(
    "call",
    [
        "Mock()",
        "mock.Mock()",
        "unittest.mock.Mock()",
        "MagicMock()",
        "mock.MagicMock()",
        "unittest.mock.MagicMock()",
    ]
)
def test_return_true_if_node_is_mock_call(call):
    node = astroid.extract_node(call)
    assert is_mock_call(node) is True


@pytest.mark.parametrize(
    "call,result",
    [
        ("patch.multiple()", True),
        ("mock.patch.multiple()", True),
        ("unittest.mock.patch.multiple()", True),
        ("multiple()", False),
    ]
)
def test_return_true_if_node_is_patch_multiple_call(call, result):
    node = astroid.extract_node(call)
    assert is_patch_multiple_call(node) is result


@pytest.mark.parametrize(
    "call,result",
    [
        ("patch.object()", True),
        ("mock.patch.object()", True),
        ("unittest.mock.patch.object()", True),
        ("object()", False),
    ]
)
def test_return_true_if_node_is_patch_object_call(call, result):
    node = astroid.extract_node(call)
    assert is_patch_object_call(node) is result


@pytest.mark.parametrize(
    "call",
    [
        "patch()",
        "mock.patch()",
        "unittest.mock.patch()",
    ]
)
def test_return_true_if_node_is_patch_call(call):
    node = astroid.extract_node(call)
    assert is_patch_call(node) is True


class TestMockChecker(pylint_testutils.CheckerTestCase):
    CHECKER_CLASS = MockChecker

    @pytest.mark.parametrize(
        'call',
        [
            'Mock()',
            'MagicMock()',
            'Mock(return_value="dont care")',
            'MagicMock(return_value="dont care")',
        ]
    )
    @pytest.mark.parametrize('module_path', import_paths)
    def test_find_mocks_with_missing_spec(self, module_path, call):
        call_node = astroid.extract_node(f'{module_path}{call}')

        with self.assertAddsMessages(
            pylint_testutils.MessageTest(
                msg_id='mock-missing-spec',
                node=call_node,
            ),
            ignore_position=True,
        ):
            self.checker.visit_call(call_node)

    @pytest.mark.parametrize(
        'call',
        [
            'Mock(spec=int)',
            'MagicMock(spec=int)',
            'Mock(spec_set=int)',
            'MagicMock(spec_set=int)',
            'Mock(5)',
            'MagicMock(5)',
        ]
    )
    @pytest.mark.parametrize('module_path', import_paths)
    def test_ignores_mocks_with_spec(self, call, module_path):
        call_node = astroid.extract_node(f'{module_path}{call}')

        with self.assertNoMessages():
            self.checker.visit_call(call_node)

    @pytest.mark.parametrize(
        'call',
        [
            'open()',
            'pathlib.Path(__file__).resolve()',
            "container('ul', class_=css_class)[0]('li')",
        ]
    )
    def test_ignores_non_mocks(self, call):
        call_node = astroid.extract_node(call)

        with self.assertNoMessages():
            self.checker.visit_call(call_node)


class TestPatchChecker(pylint_testutils.CheckerTestCase):
    CHECKER_CLASS = PatchChecker

    @pytest.mark.parametrize('module_path', import_paths)
    @pytest.mark.parametrize(
        'call',
        [
            'patch()',
            'patch.object()',
            'patch.multiple()',
        ]
    )
    def test_patch_call_has_no_spec_or_autospec(self, module_path, call):
        call_node = astroid.extract_node(f'{module_path}{call}')

        with self.assertAddsMessages(
            pylint_testutils.MessageTest(
                msg_id='patch-missing-spec',
                node=call_node,
            ),
            ignore_position=True,
        ):
            self.checker.visit_call(call_node)

    @pytest.mark.parametrize(
        'call',
        [
            'patch("some.target", spec=int)',
            'patch("some.target", autospec=True)',
            'patch("some.target", 5)',
            'patch("some.target", new=5)',
            'patch("some.target", new_callable=lambda _: 5)',
        ],
        ids=[
            'has spec argument',
            'has autospec argument',
            'has new argument',
            'has new keyword argument',
            'has new_callable argument',
        ]
    )
    @pytest.mark.parametrize('module_path', import_paths)
    def test_patch_call_has_spec_argument(self, module_path, call):
        call_node = astroid.extract_node(f'{module_path}{call}')

        with self.assertNoMessages():
            self.checker.visit_call(call_node)

    @pytest.mark.parametrize('module_path', import_paths)
    @pytest.mark.parametrize(
        'args',
        [
            '"some_module", "some_attribute", "replacement"'
            '"some_module", "some_attribute", new="replacement_object"'
        ]
    )
    def test_new_is_passed_to_patch_object(self, module_path, args):
        call_node = astroid.extract_node(f'{module_path}patch.object({args})')

        with self.assertNoMessages():
            self.checker.visit_call(call_node)

    @pytest.mark.parametrize('module_path', import_paths)
    def test_new_is_not_passed_to_patch_object(self, module_path):
        call_node = astroid.extract_node(
            f'{module_path}patch.object("some_module", "some_attribute")'
        )

        with self.assertAddsMessages(
            pylint_testutils.MessageTest(
                msg_id='patch-missing-spec',
                node=call_node,
            ),
            ignore_position=True,
        ):
            self.checker.visit_call(call_node)

    @pytest.mark.parametrize(
        'call',
        [
            'open()',
            'pathlib.Path(__file__).resolve()',
            "container('ul', class_=css_class)[0]('li')",
        ]
    )
    def test_ignores_non_patch_calls(self, call):
        call_node = astroid.extract_node(call)

        with self.assertNoMessages():
            self.checker.visit_call(call_node)
