import sys
import pathlib
import ast

import PyQt5


def add_parents(tree):
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node


def find_enums(tree):
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
