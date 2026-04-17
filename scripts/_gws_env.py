"""Resolve where OAuth tokens and client secrets are stored.

Works when running inside Hermes (hermes_constants), OpenClaw-style agents
(HERMES_HOME / OPENCLAW_HOME), or any CLI via explicit override.
"""

from __future__ import annotations

import os
from pathlib import Path


def get_state_dir() -> Path:
    """Directory for google_token.json and google_client_secret.json."""
    override = os.environ.get("GOOGLE_WORKSPACE_STATE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home()).resolve()
    except ImportError:
        pass

    for key in ("HERMES_HOME", "OPENCLAW_HOME", "OPEN_CLAW_HOME"):
        v = os.environ.get(key)
        if v:
            return Path(v).expanduser().resolve()

    # Backward compatible default used by earlier versions of this skill.
    return Path.home() / ".hermes"


def display_state_dir() -> str:
    return str(get_state_dir())
