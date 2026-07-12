from ralph_core.state import StateStore, wal_probe


def test_wal_probe_true_on_tmp(tmp_path):
    assert wal_probe(tmp_path)


def test_statestore_pragmas(tmp_path):
    store = StateStore(tmp_path / "x.db")
    assert store.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert store.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
