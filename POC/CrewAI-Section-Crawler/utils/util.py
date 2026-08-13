# Reconstructed during backup cleanup.
#
# `tools/tools/click.py`, `fill.py`, and `goto.py` import `highlight_element`,
# `remove_highlight`, `send_pre_action_screenshot`, `send_post_action_screenshot` from
# this module — the original file was missing from the backup (not recoverable). This is
# a best-effort reimplementation inferred purely from how those three files call it:
# it is NOT a recovered original, and the `socket_handler` object's real interface
# (`send_console_message`, `send_tree_structure`, ...) was never defined anywhere in the
# backup either, so calls to it are wrapped defensively — a missing/partial socket_handler
# won't crash the tool, it'll just skip that notification.
from __future__ import annotations

import os
import time
from typing import Any, Optional

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs", "screenshots")


def _safe_call(obj: Any, method: str, *args, **kwargs) -> None:
    """Call obj.method(*args, **kwargs) if it exists; swallow anything else."""
    if obj is None:
        return
    fn = getattr(obj, method, None)
    if callable(fn):
        try:
            fn(*args, **kwargs)
        except Exception as e:
            print(f"[util] socket_handler.{method} failed: {e}")


def highlight_element(page, element) -> None:
    """Draw a temporary red outline around an element handle for visual debugging."""
    if element is None:
        return
    try:
        page.evaluate(
            """(el) => {
                if (!el) return;
                el.setAttribute('data-__prev_outline', el.style.outline || '');
                el.style.outline = '3px solid red';
                el.setAttribute('data-__highlighted', 'overlayId');
            }""",
            element,
        )
    except Exception as e:
        print(f"[util] highlight_element failed: {e}")


def remove_highlight(page, overlay_id: Optional[str] = None) -> None:
    """Undo the outline applied by highlight_element on any elements carrying the marker."""
    try:
        page.evaluate(
            """() => {
                document.querySelectorAll('[data-__highlighted]').forEach((el) => {
                    el.style.outline = el.getAttribute('data-__prev_outline') || '';
                    el.removeAttribute('data-__prev_outline');
                    el.removeAttribute('data-__highlighted');
                });
            }"""
        )
    except Exception as e:
        print(f"[util] remove_highlight failed: {e}")


def _save_screenshot(page, prefix: str) -> Optional[str]:
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        path = os.path.join(SCREENSHOT_DIR, f"{prefix}_{int(time.time() * 1000)}.png")
        page.screenshot(path=path)
        return path
    except Exception as e:
        print(f"[util] screenshot failed: {e}")
        return None


def send_pre_action_screenshot(
    page,
    current_step: Optional[str] = None,
    steps: Optional[list] = None,
    socket_handler: Any = None,
    screenshot: Any = None,
    step: Optional[str] = None,
    element: Any = None,
    app_id: Optional[str] = None,
) -> Optional[str]:
    """Called by click.py right before an action is committed."""
    if steps is not None and current_step:
        steps.append(current_step)
    path = _save_screenshot(page, "pre")
    _safe_call(socket_handler, "send_console_message", app_id, f"Step: {step or current_step}")
    _safe_call(socket_handler, "send_screenshot", app_id, path)
    return path


def send_post_action_screenshot(
    page,
    current_step: Optional[str] = None,
    steps: Optional[list] = None,
    socket_handler: Any = None,
    step: Optional[str] = None,
    element: Any = None,
    action: Any = None,
    app_id: Optional[str] = None,
) -> Optional[str]:
    """Called by fill.py / goto.py right after an action completes."""
    if steps is not None and current_step:
        steps.append(current_step)
    path = _save_screenshot(page, "post")
    _safe_call(socket_handler, "send_console_message", app_id, f"Step: {step or current_step}")
    _safe_call(socket_handler, "send_screenshot", app_id, path)
    return path
