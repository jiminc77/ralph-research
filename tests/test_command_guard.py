import pytest

from ralph_core.guards import CommandDenied, PathGuard


@pytest.mark.parametrize("args", [
    ["git", "push"],
    ["git", "push", "--force", "origin", "main"],
    ["git", "--no-pager", "push"],
    ["git", "-C", ".", "push"],
    ["git", "-C", "repo", "push"],
])
def test_git_push_denied(tmp_path, args):
    with pytest.raises(CommandDenied):
        PathGuard([tmp_path], []).check_tool_call("bash", args)


@pytest.mark.parametrize("args", [["git", "status"], ["git", "commit", "-m", "x"]])
def test_benign_git_allowed(tmp_path, args):
    assert PathGuard([tmp_path], []).check_tool_call("bash", args)


def test_git_option_value_status_allowed(tmp_path):
    assert PathGuard([tmp_path], []).check_tool_call("bash", ["git", "-C", "repo", "status"])
@pytest.mark.parametrize(
    ("args", "denied"),
    [
        (["bash", "-c", "git push origin main"], True),
        (["sh", "-lc", "cd /x && git push"], True),
        (["bash", "-c", "git push; echo done"], True),
        (["bash", "-c", "echo hi && git -C sub push"], True),
        (["bash", "-c", "git status"], False),
        (["bash", "-c", "echo push"], False),
    ],
)
def test_shell_payload_git_push_guard(tmp_path, args, denied):
    guard = PathGuard([tmp_path], [])
    if denied:
        with pytest.raises(CommandDenied):
            guard.check_tool_call("bash", args)
    else:
        assert guard.check_tool_call("bash", args)
