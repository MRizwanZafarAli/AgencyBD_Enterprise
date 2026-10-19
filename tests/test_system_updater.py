"""
Unit and integration tests for SystemUpdater (Update notifications, pull/replace, git push, hot reload).
"""

from unittest.mock import MagicMock, patch
from engines.system_updater import SystemUpdater


def test_system_updater_initialization(tmp_path):
    updater = SystemUpdater(repo_dir=str(tmp_path))
    assert updater.repo_dir == tmp_path
    assert updater.GIT_AUTHOR_NAME == "MRizwanZafarAli"


def test_system_updater_get_local_status(tmp_path):
    updater = SystemUpdater(repo_dir=str(tmp_path))
    mock_responses = {
        ("rev-parse", "HEAD"): {"success": True, "stdout": "abc1234567890", "returncode": 0},
        ("branch", "--show-current"): {"success": True, "stdout": "main", "returncode": 0},
        ("log", "-1", "--pretty=format:%s||%an||%ad", "--date=iso"): {
            "success": True,
            "stdout": "feat: enterprise system||MRizwanZafarAli||2026-10-19 20:00:00",
            "returncode": 0
        },
        ("status", "--porcelain"): {"success": True, "stdout": "", "returncode": 0},
    }

    def fake_run_git(args, timeout_seconds=25):
        key = tuple(args)
        return mock_responses.get(key, {"success": True, "stdout": ""})

    with patch.object(updater, "_run_git", side_effect=fake_run_git):
        status = updater.get_local_status()
        assert status["commit"] == "abc1234567890"
        assert status["commit_short"] == "abc1234"
        assert status["branch"] == "main"
        assert status["author"] == "MRizwanZafarAli"
        assert status["is_clean"] is True


def test_system_updater_check_for_updates_behind(tmp_path):
    updater = SystemUpdater(repo_dir=str(tmp_path))

    with patch.object(updater, "get_local_status", return_value={
        "commit": "oldcommit123",
        "commit_short": "oldcom1",
        "branch": "main",
        "message": "old commit",
        "author": "MRizwanZafarAli",
        "date": "2026-10-19",
        "is_clean": True
    }), patch.object(updater, "_run_git") as mock_git:
        def side_effect(args, **kwargs):
            if "rev-list" in args and "HEAD..origin/main" in args:
                return {"success": True, "stdout": "2", "returncode": 0}
            if "rev-list" in args and "origin/main..HEAD" in args:
                return {"success": True, "stdout": "0", "returncode": 0}
            if "rev-parse" in args and "origin/main" in args:
                return {"success": True, "stdout": "newcommit456", "returncode": 0}
            if "log" in args and "HEAD..origin/main" in args:
                return {"success": True, "stdout": "newcommit456 feat: new AI model\noldcommit789 fix: bug", "returncode": 0}
            if "log" in args and "-1" in args:
                return {"success": True, "stdout": "feat: new AI model", "returncode": 0}
            return {"success": True, "stdout": "", "returncode": 0}

        mock_git.side_effect = side_effect
        result = updater.check_for_updates()
        assert result["update_available"] is True
        assert result["behind_count"] == 2
        assert result["latest_commit"] == "newcommit456"
        assert len(result["changelog"]) == 2


def test_system_updater_apply_update(tmp_path):
    updater = SystemUpdater(repo_dir=str(tmp_path))

    with patch.object(updater, "get_local_status") as mock_status, \
         patch.object(updater, "_run_git") as mock_git, \
         patch.object(updater, "_trigger_hot_reload", return_value=True):
        
        mock_status.side_effect = [
            {"commit": "old123", "commit_short": "old123", "branch": "main", "message": "old", "author": "MRizwanZafarAli"},
            {"commit": "new456", "commit_short": "new456", "branch": "main", "message": "new", "author": "MRizwanZafarAli"}
        ]

        def fake_git(args, **kwargs):
            if "diff" in args:
                return {"success": True, "stdout": "api.py\nengines/system_updater.py", "returncode": 0}
            return {"success": True, "stdout": "", "returncode": 0}

        mock_git.side_effect = fake_git

        res = updater.apply_update(auto_push=True)
        assert res["status"] == "success"
        assert res["old_commit"] == "old123"
        assert res["new_commit"] == "new456"
        assert res["changed_files_count"] == 2
        assert res["reloaded"] is True
        assert res["pushed"] is True


def test_system_updater_api_endpoints(client, make_key):
    headers = make_key("super_admin")
    mock_status = {
        "status": "success",
        "update_available": True,
        "current_commit": "curr123",
        "current_commit_short": "curr123",
        "latest_commit": "latest456",
        "latest_commit_short": "latest4",
        "behind_count": 1,
        "ahead_count": 0,
        "current_message": "Current version",
        "latest_message": "New upgrade available",
        "changelog": ["latest456 New upgrade available"],
        "branch": "main",
        "remote": "origin",
        "checked_at": "2026-10-19T21:00:00Z"
    }

    mock_apply = {
        "status": "success",
        "message": "System updated, synchronized with GitHub, and restarted.",
        "old_commit": "curr123",
        "new_commit": "latest456",
        "changed_files_count": 1,
        "changed_files": ["api.py"],
        "pushed": True,
        "reloaded": True,
    }

    with patch("api.system_updater.check_for_updates", return_value=mock_status), \
         patch("api.system_updater.apply_update", return_value=mock_apply):
        # 1. GET status
        res = client.get("/api/system/updater/status", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["update_available"] is True
        assert data["behind_count"] == 1

        # 2. POST apply
        apply_res = client.post("/api/system/updater/apply", headers=headers, json={"auto_push": True})
        assert apply_res.status_code == 200
        apply_data = apply_res.json()
        assert apply_data["status"] == "success"
        assert apply_data["new_commit"] == "latest456"
        assert apply_data["pushed"] is True
