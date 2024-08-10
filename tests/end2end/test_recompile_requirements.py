import tarfile
import pathlib
import shutil
import textwrap

import pytest

from scripts.dev import recompile_requirements


def create_package(repo_dir, name, version, dependencies=[]):
    # Minimal package structure as per https://packaging-guide.openastronomy.org/en/latest/minimal.html
    # Install like pip3 install -U --extra-index-url file:///{repo_dir} pkg
    # `--index-url` doesn't seem to work because this package format seems to
    # need setuptools to install.
    pkg_dir = repo_dir / "raw" / name
    (pkg_dir / name).mkdir(exist_ok=True, parents=True)
    init_file = pkg_dir / name / "__init__.py"
    init_file.write_text(f"__version__ = '{version}'")
    project_file = pkg_dir / "pyproject.toml"
    project_file.write_text(
        f"""
[project]
name = "{name}"
dependencies = {dependencies}
version = "{version}"
"""
    )

    # Repo structure:
    # /
    # /raw/pkg/ - source of pkg
    # /simple/index.html - list of packages
    # /simple/pkg/pkg-1.0.0.tar.gz - installable taball for pkg
    # /simple/pkg/index.html - list of artifacts for pkg
    simple = repo_dir / "simple"

    install_dir = simple / name
    install_dir.mkdir(exist_ok=True, parents=True)

    def fname_filter(info):
        info.name = str(("/" / pathlib.Path(info.name)).relative_to(pkg_dir))
        return info

    tarball = install_dir / f"{name}-{version}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tf:
        tf.add(pkg_dir, filter=fname_filter)
    with (install_dir / "index.html").open(mode="w") as file_index:
        file_index.write("<!DOCTYPE html>\n<html>\n<body>\n")
        file_index.write(f'<a href="{tarball.parts[-1]}">{name}-{version}</a>\n')
        file_index.write("</body>\n</html>\n")

    # Regenerate repo index for every new package
    with (simple / "index.html").open(mode="w") as repo_index:
        repo_index.write("<!DOCTYPE html>\n<html>\n<body>\n")
        for package in simple.glob("**/*tar.gz"):
            repo_index.write(f'<a href="{package.parent.parts[-1]}/">{package.parent.parts[-1]}</a>\n')
        repo_index.write("</body>\n</html>\n")


@pytest.mark.parametrize("reqs, expected", [
    (
        """
        qute-test-1
        qute-test-2
        """,
        """
        qute-test-1==1.0.0
        qute-test-2==1.0.0
        """,
    ),
])
def disabled_test_markers_real_pip_and_venv(reqs, expected, tmp_path, monkeypatch):
    """Very slow test.

    Slow bits are a) downloading real packages (pip, setuptools, wheel, uv)
    from pypi.org b) creating the venv.
    """
    repo_dir = tmp_path / "test_repo"
    monkeypatch.setenv("PIP_EXTRA_INDEX_URL", f"file://{repo_dir}/simple/")
    monkeypatch.setenv("UV_EXTRA_INDEX_URL", f"file://{repo_dir}/simple/")

    create_package(repo_dir, "qute-test-1", "1.0.0")
    create_package(repo_dir, "qute-test-2", "1.0.0", dependencies=["qute-test-1==1.0.0"])

    monkeypatch.setattr(recompile_requirements, "REQ_DIR", tmp_path)

    (tmp_path / "requirements-test.txt-raw").write_text(
        textwrap.dedent(reqs)
    )
    recompile_requirements.build_requirements("test", mode="compile")

    result = (tmp_path / "requirements-test.txt").read_text()
    assert result.strip() == f"{recompile_requirements.PREAMBLE}{textwrap.dedent(expected).strip()}"


@pytest.mark.parametrize("reqs, initial_compiled, expected", [
    (
        """
        PyQt5==5.15.2
        PyQtWebEngine==5.15.2
        #@ filter: PyQt5 == 5.15.2
        #@ filter: PyQtWebEngine == 5.15.2
        """,
        """
        pyqt5==5.15.2
        PyQtWebEngine==5.15.2
        """,
        """
        pyqt5==5.15.2  # rq.filter: == 5.15.2
        PyQtWebEngine==5.15.2  # rq.filter: == 5.15.2
        """,
    ),
    (
        """
        PyQt5 >= 5.15, < 5.16
        PyQtWebEngine >= 5.15, < 5.16
        #@ filter: PyQt5 < 5.16
        #@ filter: PyQtWebEngine < 5.16
        """,
        """
        pyqt5==5.15.10
        PyQtWebEngine==5.15.6
        """,
        """
        pyqt5==5.15.10  # rq.filter: < 5.16
        PyQtWebEngine==5.15.6  # rq.filter: < 5.16
        """,
    ),
    (
        """
        before
        #@ add: # Unpinned due to recompile_requirements.py limitations
        #@ add: pyobjc-core ; sys_platform=="darwin"
        after
        """,
        """
        before
        after
        """,
        """
        before
        after
        # Unpinned due to recompile_requirements.py limitations
        pyobjc-core ; sys_platform=="darwin"
        """,
    ),
    (
        """
        foo
        Jinja2
        #@ ignore: Jinja2
        """,
        """
        foo
        jinja2
        """,
        """
        foo
        # jinja2
        """,
    ),
    (
        """
        importlib_resources
        typed_ast
        #@ markers: importlib_resources python_version=="3.8.*"
        #@ markers: typed_ast python_version<"3.8"
        """,
        """
        importlib-resources
        typed-ast
        """,
        """
        importlib-resources ; python_version=="3.8.*"
        typed-ast ; python_version<"3.8"
        """,
    ),
    (
        """
        ./scripts/dev/pylint_checkers
        #@ replace: qute[_-]pylint.* ./scripts/dev/pylint_checkers
        """,
        """
        qute-pylint@/home/runner/qutebrowser/scripts/dev/pylint_checkers
        """,
        """
        ./scripts/dev/pylint_checkers
        """,
    ),
])
def test_markers_in_comments(reqs, initial_compiled, expected, tmp_path, monkeypatch):
    """Ensure that each of the comments support in read_comments() works.

    Also tests that packages where their names have been normalized in the
    initial_compiled output still get processed as expected.
    """
    monkeypatch.setattr(recompile_requirements, "REQ_DIR", tmp_path)
    # Write the raw requirements file with comments in.
    (tmp_path / "requirements-test.txt-raw").write_text(
        textwrap.dedent(reqs)
    )
    # Mock the actual requirements compilation that involves pip and venv
    # with raw compiled requirements without our post processing.
    monkeypatch.setattr(
        recompile_requirements,
        "get_updated_requirements_compile",
        lambda *args: textwrap.dedent(initial_compiled).strip(),
    )

    recompile_requirements.build_requirements("test", mode="compile")

    result = (tmp_path / "requirements-test.txt").read_text()
    assert result.strip() == f"{recompile_requirements.PREAMBLE}{textwrap.dedent(expected).strip()}"
