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
