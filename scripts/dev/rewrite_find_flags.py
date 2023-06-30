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


"""Find all PyQt flag instances."""

import pathlib
import ast

import PyQt5


def find_flags(tree):
    """Find all PyQt flags in an AST tree."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name != "__init__":
            continue

        if len(node.args.args) == 1:
            continue

        annotation = node.args.args[1].annotation

        if not isinstance(annotation, ast.Subscript):
            continue

        assert isinstance(annotation.value, ast.Attribute)
        assert isinstance(annotation.value.value, ast.Name)
        assert annotation.value.value.id == "typing"
        if annotation.value.attr != "Union":
            continue

        assert isinstance(annotation.slice, ast.Tuple)
        elts = annotation.slice.elts

        if not all(isinstance(n, ast.Constant) for n in elts):
            continue

        names = [n.value for n in elts]
        if not all("." in name for name in names):
            continue

        yield names


def main():
    pyqt5_path = pathlib.Path(PyQt5.__file__).parent
    pyi_files = list(pyqt5_path.glob("*.pyi"))
    if not pyi_files:
        print("No .pyi-files found for your PyQt installation!")
    for path in pyi_files:
        #print(f"# {path.stem}")

        tree = ast.parse(
            path.read_text(),
            filename=str(path),
            type_comments=True,
        )

        for flag, enum in find_flags(tree):
            print(flag, enum)


if __name__ == '__main__':
    main()
