"""Shared helpers used by both setup.py and google_api.py.

Keeping one module for credential loading, scope validation and error
rendering avoids drift between the two entry points.
"""

from __future__ import annotations

import json
import sys
from functools import wraps
from typing import Any, Callable, List

try:
    from .scopes import SCOPES
except ImportError:  # running as a script (not installed)
    from scopes import SCOPES  # type: ignore


def missing_scopes_from_payload(payload: dict) -> List[str]:
    """Return scopes required by this skill but absent from a token payload."""
    raw = payload.get("scopes") or payload.get("scope")
    if not raw:
        return []
    if isinstance(raw, str):
        granted = {s.strip() for s in raw.split() if s.strip()}
    else:
        granted = {str(s).strip() for s in raw if str(s).strip()}
    return sorted(scope for scope in SCOPES if scope not in granted)


def format_missing_scopes(missing: List[str]) -> str:
    bullets = "\n".join(f"  - {scope}" for scope in missing)
    return (
        "Token is valid but missing required Google Workspace scopes:\n"
        f"{bullets}\n"
        "Run `gws-setup --auth-url` and `--auth-code` again from the same profile "
        "directory to refresh consent."
    )


def print_json(obj: Any) -> None:
    """Emit JSON output deterministically (UTF-8, indented)."""
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def api_call(func: Callable) -> Callable:
    """Decorator: convert Google API / JSON errors into structured stderr output.

    Every CLI action should be wrapped so that agents get a predictable shape
    instead of a raw Python traceback.
    """

    @wraps(func)
    def wrapper(args):
        try:
            return func(args)
        except Exception as exc:  # noqa: BLE001 — we want a CLI-level safety net
            payload = {
                "error": type(exc).__name__,
                "message": str(exc),
            }
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status is not None:
                payload["http_status"] = status
            try:
                import googleapiclient.errors as ge

                if isinstance(exc, ge.HttpError):
                    try:
                        details = json.loads(exc.content.decode("utf-8"))
                        payload["google"] = details
                    except Exception:
                        pass
            except Exception:
                pass
            print(json.dumps({"ok": False, **payload}, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(2)

    return wrapper
