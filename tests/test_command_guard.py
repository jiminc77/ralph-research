import pytest

from ralph_core.guards import CommandDenied, PathGuard


@pytest.mark.parametrize("args", [
    ["git", "push"],
    ["git", "push", "--force", "origin", "main"],
    ["git", "--no-pager", "push"],
    ["git", "-C", ".", "push"],
])
def test_git_push_denied(tmp_path, args):
    with pytest.raises(CommandDenied):
        PathGuard([tmp_path], []).check_tool_call("bash", args)


@pytest.mark.parametrize("args", [["git", "status"], ["git", "commit", "-m", "x"]])
def test_benign_git_allowed(tmp_path, args):
    assert PathGuard([tmp_path], []).check_tool_call("bash", args)
