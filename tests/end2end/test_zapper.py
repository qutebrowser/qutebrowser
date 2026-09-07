# SPDX-FileCopyrightText: Freya Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""End-to-end tests for the zapper element-hiding tool."""

import pytest
from collections.abc import Generator
from typing import Any

pytestmark = pytest.mark.flaky(reruns=3)


@pytest.fixture(autouse=True)
def _zapper_cleanup(quteproc: Any) -> Generator[None]:
    yield
    try:
        quteproc.send_cmd(':zapper-restore')
    except Exception:
        pass


def _element_state(quteproc: Any, element_id: str) -> str:
    """Return the state of an element."""
    marker = f'qute-{element_id}'

    script = f"""
        (function() {{
            const el = document.getElementById("{element_id}");

            if (!el) {{
                console.log("{marker}:missing");
                return;
            }}

            const style = window.getComputedStyle(el);

            const visible =
                style.display !== "none" &&
                style.visibility !== "hidden" &&
                el.offsetParent !== null;

            console.log(
                visible
                    ? "{marker}:visible"
                    : "{marker}:hidden"
            );
        }})();
    """

    quteproc.send_cmd(':jseval ' + script, escape=False)

    return quteproc.wait_for_js(f'{marker}:*').message


def assert_visible(quteproc: Any, element_id: str) -> None:
    message = _element_state(quteproc, element_id)

    assert message.endswith(':visible'), (
        f'{element_id} should be visible. Got: {message}'
    )


def assert_not_visible(quteproc: Any, element_id: str) -> None:

    # Wait in-page for the element to become hidden/missing, as applying
    # zapper restore rules can be asynchronous after reload.
    marker = f'qute-{element_id}'

    script = f"""
        (function() {{
            const id = "{element_id}";
            const marker = "{marker}";

            function check() {{
                const el = document.getElementById(id);
                if (!el) {{ console.log(marker + ':missing'); return true; }}
                const style = window.getComputedStyle(el);
                const visible =
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    el.offsetParent !== null;
                if (!visible) {{ console.log(marker + ':hidden'); return true; }}
                return false;
            }}

            if (check()) return;

            try {{
                const obs = new MutationObserver(function() {{ if (check()) obs.disconnect(); }});
                obs.observe(document, {{ attributes: true, childList: true, subtree: true }});
            }} catch (e) {{ /* ignore */ }}

            // Fallback: after timeout, report current state
            setTimeout(function() {{
                const el = document.getElementById(id);
                if (!el) {{ console.log(marker + ':missing'); return; }}
                const style = window.getComputedStyle(el);
                const visible =
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    el.offsetParent !== null;
                console.log(marker + (visible ? ':visible' : ':hidden'));
            }}, 3000);
        }})();
    """

    quteproc.send_cmd(':jseval ' + script, escape=False)
    message = quteproc.wait_for_js(f'{marker}:*').message

    assert (
        message.endswith(':hidden') or
        message.endswith(':missing')
    ), f'{element_id} should not be visible. Got: {message}'


def enable_zapper(quteproc: Any) -> None:
    quteproc.send_cmd(':zapper')
    quteproc.wait_for(message='Zapper enabled*')


def disable_zapper(quteproc: Any) -> None:
    quteproc.send_cmd(':zapper')
    quteproc.wait_for(message='Zapper disabled*')


def goto(quteproc: Any, path: str) -> None:
    """Open `path` and wait for it to finish loading."""
    quteproc.open_path(path)
    #quteproc.wait_for_load_finished(path)


def test_zapper_enters_mode(quteproc: Any) -> None:
    goto(quteproc, 'data/zapper.html')

    enable_zapper(quteproc)


def test_zapper_exits_mode(quteproc: Any) -> None:
    goto(quteproc, 'data/zapper.html')

    enable_zapper(quteproc)
    disable_zapper(quteproc)


def test_zapper_toggle_mode_multiple_times(quteproc: Any) -> None:
    goto(quteproc, 'data/zapper.html')

    enable_zapper(quteproc)
    disable_zapper(quteproc)

    enable_zapper(quteproc)

    quteproc.click_element_by_id('button1')

    disable_zapper(quteproc)

    assert_not_visible(quteproc, 'button1')


def test_zapper_without_save(quteproc: Any) -> None:
    goto(quteproc, 'data/zapper.html')

    enable_zapper(quteproc)

    quteproc.click_element_by_id('button1')

    disable_zapper(quteproc)

    assert_not_visible(quteproc, 'button1')


def test_zapper_remove_multiple_elements(quteproc: Any) -> None:
    goto(quteproc, 'data/zapper.html')

    enable_zapper(quteproc)

    quteproc.click_element_by_id('button1')
    quteproc.click_element_by_id('button2')

    disable_zapper(quteproc)

    assert_not_visible(quteproc, 'button1')
    assert_not_visible(quteproc, 'button2')


def test_zapper_without_save_leave_and_back_to_site(quteproc: Any) -> None:
    goto(quteproc, 'data/zapper.html')

    enable_zapper(quteproc)

    quteproc.click_element_by_id('button1')

    disable_zapper(quteproc)

    assert_not_visible(quteproc, 'button1')

    goto(quteproc, 'data/email_address.html')

    quteproc.send_cmd(':back')

    quteproc.wait_for_load_finished('data/zapper.html')

    assert_visible(quteproc, 'button1')


def test_zapper_with_save_and_restore(quteproc: Any) -> None:
    goto(quteproc, 'data/zapper.html')

    enable_zapper(quteproc)

    quteproc.click_element_by_id('button1')

    quteproc.send_cmd(':zapper-save')

    disable_zapper(quteproc)

    assert_not_visible(quteproc, 'button1')

    quteproc.send_cmd(':zapper-restore')

    assert_visible(quteproc, 'button1')


def test_zapper_restore_after_reload(quteproc: Any) -> None:
    goto(quteproc, 'data/zapper.html')

    enable_zapper(quteproc)

    quteproc.click_element_by_id('button1')

    quteproc.send_cmd(':zapper-save')

    quteproc.send_cmd(':reload')
    # Wait for the page to finish loading so zapper restore runs reliably
    quteproc.wait_for_load_finished('data/zapper.html')

    assert_not_visible(quteproc, 'button1')

    quteproc.send_cmd(':zapper-restore')

    assert_visible(quteproc, 'button1')


def test_zapper_save_multiple_elements_and_restore(quteproc: Any) -> None:
    goto(quteproc, 'data/zapper.html')

    enable_zapper(quteproc)

    quteproc.click_element_by_id('button1')
    quteproc.click_element_by_id('button2')

    quteproc.send_cmd(':zapper-save')

    disable_zapper(quteproc)

    assert_not_visible(quteproc, 'button1')
    assert_not_visible(quteproc, 'button2')

    quteproc.send_cmd(':zapper-restore')

    assert_visible(quteproc, 'button1')
    assert_visible(quteproc, 'button2')


def test_all_comands_multiple_sites(quteproc: Any) -> None:
    goto(quteproc, 'data/zapper.html')

    enable_zapper(quteproc)

    quteproc.click_element_by_id('button1')

    disable_zapper(quteproc)

    quteproc.send_cmd(':zapper-save')

    assert_not_visible(quteproc, 'button1')

    goto(quteproc, 'data/zapper2.html')

    enable_zapper(quteproc)

    quteproc.click_element_by_id('button2')

    disable_zapper(quteproc)

    quteproc.send_cmd(':zapper-save')

    assert_not_visible(quteproc, 'button2')

    quteproc.send_cmd(':back')

    quteproc.wait_for_load_finished('data/zapper.html')

    assert_not_visible(quteproc, 'button1')

    quteproc.send_cmd(':forward')

    quteproc.wait_for_load_finished('data/zapper2.html')

    assert_not_visible(quteproc, 'button2')

    quteproc.send_cmd(':zapper-restore')
    quteproc.send_cmd(':back')

    quteproc.wait_for_load_finished('data/zapper.html')

    quteproc.send_cmd(':zapper-restore')

    assert_visible(quteproc, 'button1')

    quteproc.send_cmd(':forward')

    quteproc.wait_for_load_finished('data/zapper2.html')

    assert_visible(quteproc, 'button2')
