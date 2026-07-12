"""Allowlist-constructed worker environments. Never inherit-then-filter."""
from __future__ import annotations

import os
import re


class EnvLeakError(Exception):
    pass


_SAFE_PASSTHROUGH = {"PATH", "HOME", "LANG", "TZ"}
_SECRET_NAME = re.compile(
    r"^(AWS_|GITHUB_|GH_|OPENAI_|ANTHROPIC_|.*TOKEN|.*SECRET|.*KEY$|.*PASSWORD)"
)


def build_env(role, allowlist, extra):
    """Build a worker environment strictly from `allowlist` plus `extra`.

    Allowlist values of None copy from os.environ only for the small safe
    passthrough set. Any resulting name matching the secret denylist raises
    EnvLeakError instead of being silently dropped.
    """
    env: dict[str, str] = {}
    for name, value in allowlist.items():
        if value is None:
            if name in _SAFE_PASSTHROUGH and name in os.environ:
                env[name] = os.environ[name]
        else:
            env[name] = str(value)
    env.update({str(key): str(value) for key, value in extra.items()})
    for name in env:
        if _SECRET_NAME.match(name):
            raise EnvLeakError(name)
    return env


def redact(text, env):
    """Replace long environment values embedded in `text` with a marker."""
    for value in env.values():
        if len(value) >= 32:
            text = text.replace(value, "[redacted]")
    return text
