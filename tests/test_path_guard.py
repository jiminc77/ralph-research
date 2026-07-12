from ralph_core.guards import PathGuard


def test_hidden_root_denied_incl_symlink(tmp_path):
    allowed = tmp_path / "allowed"
    hidden = allowed / ".hidden"
    allowed.mkdir()
    hidden.mkdir()
    (allowed / "link").symlink_to(hidden, target_is_directory=True)
    guard = PathGuard([allowed], [hidden])
    assert not guard.check_path(allowed / "link" / "x")


def test_traversal_denied(tmp_path):
    allowed = tmp_path / "allowed"
    hidden = tmp_path / "hidden"
    allowed.mkdir()
    hidden.mkdir()
    guard = PathGuard([allowed], [hidden])
    assert not guard.check_path(allowed / ".." / "hidden" / "x")


def test_allowed_path_passes(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    path = allowed / "ok"
    path.write_text("")
    assert PathGuard([allowed], []).check_path(path)
