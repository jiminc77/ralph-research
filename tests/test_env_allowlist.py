import pytest

from ralph_core.envs import EnvLeakError, build_env, redact


def test_denylisted_env_absent(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "bad")
    monkeypatch.setenv("MY_TOKEN", "bad")
    monkeypatch.setenv("GITHUB_TOKEN", "bad")
    env = build_env("x", {"PATH": None, "X": "yes"}, {})
    assert "PATH" in env
    assert not {"AWS_SECRET_ACCESS_KEY", "MY_TOKEN", "GITHUB_TOKEN"} & env.keys()


def test_explicit_secret_name_raises():
    with pytest.raises(EnvLeakError):
        build_env("x", {"DEPLOY_SECRET": "x"}, {})


def test_redact_masks_long_values():
    secret = "a" * 32
    assert redact(f"x{secret}", {"x": secret}) == "x[redacted]"
