# Copyright 2021-2022 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Find all PyQt enum instances."""


import pathlib
import ast

import PyQt5


def find_enums(tree):
    """Find all PyQt enums in an AST tree."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if node.type_comment is None:
            continue
        if '.' not in node.type_comment:
            continue
        if not node.type_comment.startswith("Q"):
            continue
        comment = node.type_comment.strip("'")
        mod, cls = comment.rsplit(".", maxsplit=1)
        assert len(node.targets) == 1
        name = node.targets[0].id
        yield (mod, cls, name)


def main():
    pyqt5_path = pathlib.Path(PyQt5.__file__).parent
    pyi_files = list(pyqt5_path.glob("*.pyi"))
    if not pyi_files:
        print("No .pyi-files found for your PyQt installation!")
    for path in pyi_files:
        print(f"# {path.stem}")
        tree = ast.parse(
            path.read_text(),
            filename=str(path),
            type_comments=True,
        )
        for mod, cls, name in find_enums(tree):
            old = f"{mod}.{name}"
            new = f"{mod}.{cls}.{name}"
            print(f"{old} {new}")


if __name__ == '__main__':
    main()
