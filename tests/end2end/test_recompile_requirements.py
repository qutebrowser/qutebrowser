import textwrap

import pytest

from scripts.dev import recompile_requirements


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
