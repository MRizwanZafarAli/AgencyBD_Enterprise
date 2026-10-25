import sqlite3
import pytest
from scripts.backup_db import backup


def test_backup_copies_data_and_rotates(tmp_path):
    src = tmp_path / "src.db"
    c = sqlite3.connect(src)
    c.execute("create table t(x)"); c.execute("insert into t values (42)"); c.commit(); c.close()
    dest = tmp_path / "b"
    for _ in range(4):
        out = backup(src, dest, keep=2)
    assert len(list(dest.glob("agency_bd-*.db"))) == 2
    assert sqlite3.connect(out).execute("select x from t").fetchone()[0] == 42


def test_backup_of_missing_db_fails(tmp_path):
    with pytest.raises(Exception):
        backup(tmp_path / "nope.db", tmp_path / "b")


def test_restore_replaces_the_database_keeps_the_old_one_and_refuses_corrupt_backups(tmp_path):
    from scripts.backup_db import backup
    from scripts.restore_db import restore
    live = tmp_path / "live.db"
    c = sqlite3.connect(live); c.execute("create table t(x)"); c.execute("insert into t values (1)"); c.commit(); c.close()
    snap = backup(live, tmp_path / "b")
    c = sqlite3.connect(live); c.execute("insert into t values (2)"); c.commit(); c.close()          # data created after the backup
    aside = restore(snap, live)
    assert [r[0] for r in sqlite3.connect(live).execute("select x from t order by x")] == [1]        # back to the backup's state
    assert [r[0] for r in sqlite3.connect(aside).execute("select x from t order by x")] == [1, 2]    # nothing was destroyed
    bad = tmp_path / "bad.db"; bad.write_bytes(b"not a database")
    with pytest.raises(Exception):
        restore(bad, live)
    assert [r[0] for r in sqlite3.connect(live).execute("select x from t order by x")] == [1]        # a bad backup never touches the live db
