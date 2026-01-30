"""Tests for AttacksDatabase - unified attack data storage."""

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.attacks_db import AttacksDatabase, _now_iso, _now_unix


class TestHelperFunctions(unittest.TestCase):
    """Tests for module-level helper functions."""

    def test_now_iso_format(self):
        """Should return ISO8601 formatted timestamp."""
        result = _now_iso()
        # Should contain date and time parts
        self.assertIn("T", result)
        self.assertIn("-", result)
        self.assertIn(":", result)

    def test_now_unix_is_float(self):
        """Should return Unix timestamp as float."""
        result = _now_unix()
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)


class TestDatabaseInit(unittest.TestCase):
    """Tests for AttacksDatabase initialization."""

    def test_creates_empty_db_if_not_exists(self):
        """Should create empty database structure if file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db.json"
            db = AttacksDatabase(db_path)

            self.assertEqual(db._data["version"], "2.0")
            self.assertIn("stats", db._data)
            self.assertIn("ips", db._data)
            self.assertIn("whitelist", db._data)
            self.assertIn("blacklist", db._data)
            self.assertEqual(db._data["ips"], {})

    def test_loads_existing_db(self):
        """Should load existing database from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db.json"

            # Create existing database
            existing_data = {
                "version": "2.0",
                "created_at": "2024-01-01T00:00:00",
                "last_updated": "2024-01-01T00:00:00",
                "stats": {"total_ips": 1},
                "metadata": {"log_positions": {}},
                "whitelist": [],
                "blacklist": [],
                "ips": {"1.2.3.4": {"danger_score": 50}}
            }
            with open(db_path, 'w') as f:
                json.dump(existing_data, f)

            db = AttacksDatabase(db_path)

            self.assertEqual(db._data["stats"]["total_ips"], 1)
            self.assertIn("1.2.3.4", db._data["ips"])

    def test_handles_corrupted_db(self):
        """Should create empty database if existing file is corrupted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db.json"

            # Create corrupted file
            with open(db_path, 'w') as f:
                f.write("not valid json {{{")

            db = AttacksDatabase(db_path)

            # Should have fresh empty structure
            self.assertEqual(db._data["version"], "2.0")
            self.assertEqual(db._data["ips"], {})


class TestSave(unittest.TestCase):
    """Tests for save() method."""

    def test_saves_to_disk(self):
        """Should save database to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db.json"
            db = AttacksDatabase(db_path)

            db.record_attempt("1.2.3.4", "sshd")
            result = db.save()

            self.assertTrue(result)
            self.assertTrue(db_path.exists())

            # Verify saved data
            with open(db_path) as f:
                saved_data = json.load(f)
            self.assertIn("1.2.3.4", saved_data["ips"])

    def test_skips_save_if_not_dirty(self):
        """Should skip save if no changes were made."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db.json"
            db = AttacksDatabase(db_path)
            db.save()  # Initial save
            db._dirty = False

            # Remove file to verify save is skipped
            db_path.unlink()
            result = db.save()

            self.assertTrue(result)
            self.assertFalse(db_path.exists())  # Should not recreate

    def test_creates_parent_directories(self):
        """Should create parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "deep" / "test.db.json"
            db = AttacksDatabase(db_path)
            db._dirty = True

            result = db.save()

            self.assertTrue(result)
            self.assertTrue(db_path.exists())


class TestIPOperations(unittest.TestCase):
    """Tests for IP CRUD operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db.json"
        self.db = AttacksDatabase(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_get_ip_returns_none_for_unknown(self):
        """Should return None for unknown IP."""
        result = self.db.get_ip("1.2.3.4")
        self.assertIsNone(result)

    def test_get_ip_returns_record(self):
        """Should return IP record if exists."""
        self.db.record_attempt("1.2.3.4", "sshd")

        result = self.db.get_ip("1.2.3.4")

        self.assertIsNotNone(result)
        self.assertEqual(result["attempts"]["total"], 1)

    def test_upsert_ip_creates_new(self):
        """Should create new IP record if doesn't exist."""
        self.db.upsert_ip("1.2.3.4", {"danger_score": 50})

        result = self.db.get_ip("1.2.3.4")

        self.assertEqual(result["danger_score"], 50)
        self.assertEqual(self.db._data["stats"]["total_ips"], 1)

    def test_upsert_ip_updates_existing(self):
        """Should update existing IP record."""
        self.db.upsert_ip("1.2.3.4", {"danger_score": 50})
        self.db.upsert_ip("1.2.3.4", {"danger_score": 75, "status": "threat"})

        result = self.db.get_ip("1.2.3.4")

        self.assertEqual(result["danger_score"], 75)
        self.assertEqual(result["status"], "threat")

    def test_upsert_ip_deep_merges(self):
        """Should deep merge nested dictionaries."""
        self.db.upsert_ip("1.2.3.4", {"geo": {"country": "US"}})
        self.db.upsert_ip("1.2.3.4", {"geo": {"city": "New York"}})

        result = self.db.get_ip("1.2.3.4")

        self.assertEqual(result["geo"]["country"], "US")
        self.assertEqual(result["geo"]["city"], "New York")


class TestEventRecording(unittest.TestCase):
    """Tests for event recording methods."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db.json"
        self.db = AttacksDatabase(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_record_attempt_creates_ip(self):
        """Should create IP record if doesn't exist."""
        self.db.record_attempt("1.2.3.4", "sshd")

        record = self.db.get_ip("1.2.3.4")

        self.assertIsNotNone(record)
        self.assertEqual(record["attempts"]["total"], 1)
        self.assertEqual(record["attempts"]["by_jail"]["sshd"], 1)

    def test_record_attempt_increments(self):
        """Should increment attempt counters."""
        self.db.record_attempt("1.2.3.4", "sshd")
        self.db.record_attempt("1.2.3.4", "sshd")
        self.db.record_attempt("1.2.3.4", "recidive")

        record = self.db.get_ip("1.2.3.4")

        self.assertEqual(record["attempts"]["total"], 3)
        self.assertEqual(record["attempts"]["by_jail"]["sshd"], 2)
        self.assertEqual(record["attempts"]["by_jail"]["recidive"], 1)

    def test_record_attempt_updates_global_stats(self):
        """Should update global statistics."""
        self.db.record_attempt("1.2.3.4", "sshd")

        self.assertEqual(self.db._data["stats"]["total_attempts"], 1)

    def test_record_ban_sets_active(self):
        """Should mark IP as actively banned."""
        self.db.record_ban("1.2.3.4", "sshd", duration=600)

        record = self.db.get_ip("1.2.3.4")

        self.assertTrue(record["bans"]["active"])
        self.assertEqual(record["bans"]["current_jail"], "sshd")
        self.assertEqual(record["bans"]["current_ban_duration"], 600)
        self.assertEqual(record["bans"]["total"], 1)
        self.assertEqual(record["status"], "active_ban")

    def test_record_ban_adds_history(self):
        """Should add entry to ban history."""
        self.db.record_ban("1.2.3.4", "sshd", duration=600, trigger_count=5)

        record = self.db.get_ip("1.2.3.4")

        self.assertEqual(len(record["bans"]["history"]), 1)
        self.assertEqual(record["bans"]["history"][0]["jail"], "sshd")
        self.assertEqual(record["bans"]["history"][0]["duration"], 600)
        self.assertEqual(record["bans"]["history"][0]["trigger_count"], 5)

    def test_record_unban_clears_active(self):
        """Should clear active ban status."""
        self.db.record_ban("1.2.3.4", "sshd", duration=600)
        self.db.record_unban("1.2.3.4", "sshd")

        record = self.db.get_ip("1.2.3.4")

        self.assertFalse(record["bans"]["active"])
        self.assertIsNone(record["bans"]["current_jail"])
        self.assertEqual(record["status"], "unbanned")

    def test_record_unban_ignores_unknown_ip(self):
        """Should do nothing for unknown IP."""
        self.db.record_unban("unknown.ip", "sshd")
        # Should not raise error
        self.assertIsNone(self.db.get_ip("unknown.ip"))

    def test_record_unban_updates_history(self):
        """Should update end time in ban history."""
        self.db.record_ban("1.2.3.4", "sshd")
        self.db.record_unban("1.2.3.4", "sshd")

        record = self.db.get_ip("1.2.3.4")

        self.assertIsNotNone(record["bans"]["history"][0]["end"])


class TestGeoData(unittest.TestCase):
    """Tests for geolocation data methods."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db.json"
        self.db = AttacksDatabase(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_set_geo_creates_ip(self):
        """Should create IP record if doesn't exist."""
        self.db.set_geo("1.2.3.4", "United States", "Google LLC",
                        country_code="US", asn="AS15169", city="Mountain View")

        record = self.db.get_ip("1.2.3.4")

        self.assertEqual(record["geo"]["country"], "United States")
        self.assertEqual(record["geo"]["org"], "Google LLC")
        self.assertEqual(record["geo"]["country_code"], "US")
        self.assertEqual(record["geo"]["asn"], "AS15169")
        self.assertEqual(record["geo"]["city"], "Mountain View")

    def test_set_user_comment(self):
        """Should set user comment."""
        self.db.set_user_comment("1.2.3.4", "Known attacker")

        record = self.db.get_ip("1.2.3.4")

        self.assertEqual(record["user_comment"], "Known attacker")


class TestWhitelistBlacklist(unittest.TestCase):
    """Tests for whitelist/blacklist operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db.json"
        self.db = AttacksDatabase(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_add_to_whitelist(self):
        """Should add IP to whitelist."""
        self.db.add_to_whitelist("1.2.3.4", reason="Trusted server")

        self.assertTrue(self.db.is_whitelisted("1.2.3.4"))
        whitelist = self.db.get_whitelist()
        self.assertEqual(len(whitelist), 1)
        self.assertEqual(whitelist[0]["ip"], "1.2.3.4")
        self.assertEqual(whitelist[0]["reason"], "Trusted server")

    def test_whitelist_prevents_duplicates(self):
        """Should not add duplicate whitelist entries."""
        self.db.add_to_whitelist("1.2.3.4")
        self.db.add_to_whitelist("1.2.3.4")

        whitelist = self.db.get_whitelist()
        self.assertEqual(len(whitelist), 1)

    def test_whitelist_updates_ip_status(self):
        """Should update IP status to 'whitelisted'."""
        self.db.record_attempt("1.2.3.4", "sshd")
        self.db.add_to_whitelist("1.2.3.4")

        record = self.db.get_ip("1.2.3.4")
        self.assertEqual(record["status"], "whitelisted")

    def test_add_to_blacklist(self):
        """Should add IP to blacklist."""
        self.db.add_to_blacklist("1.2.3.4", reason="Persistent attacker")

        self.assertTrue(self.db.is_blacklisted("1.2.3.4"))
        blacklist = self.db.get_blacklist()
        self.assertEqual(len(blacklist), 1)
        self.assertEqual(blacklist[0]["reason"], "Persistent attacker")

    def test_is_whitelisted_returns_false_for_unknown(self):
        """Should return False for non-whitelisted IP."""
        self.assertFalse(self.db.is_whitelisted("1.2.3.4"))

    def test_is_blacklisted_returns_false_for_unknown(self):
        """Should return False for non-blacklisted IP."""
        self.assertFalse(self.db.is_blacklisted("1.2.3.4"))


class TestQueries(unittest.TestCase):
    """Tests for query methods."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db.json"
        self.db = AttacksDatabase(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_get_all_ips(self):
        """Should return all IP records."""
        self.db.record_attempt("1.1.1.1", "sshd")
        self.db.record_attempt("2.2.2.2", "sshd")

        result = self.db.get_all_ips()

        self.assertEqual(len(result), 2)
        self.assertIn("1.1.1.1", result)
        self.assertIn("2.2.2.2", result)

    def test_get_active_bans(self):
        """Should return only actively banned IPs."""
        self.db.record_ban("1.1.1.1", "sshd")
        self.db.record_ban("2.2.2.2", "sshd")
        self.db.record_unban("2.2.2.2", "sshd")

        result = self.db.get_active_bans()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ip"], "1.1.1.1")

    def test_get_top_threats(self):
        """Should return IPs sorted by danger score."""
        self.db.upsert_ip("1.1.1.1", {"danger_score": 30})
        self.db.upsert_ip("2.2.2.2", {"danger_score": 80})
        self.db.upsert_ip("3.3.3.3", {"danger_score": 50})

        result = self.db.get_top_threats(limit=2)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["ip"], "2.2.2.2")
        self.assertEqual(result[1]["ip"], "3.3.3.3")

    def test_get_recent_activity(self):
        """Should return IPs sorted by last_seen."""
        self.db._data["ips"]["1.1.1.1"] = {"last_seen": "2024-01-01T00:00:00"}
        self.db._data["ips"]["2.2.2.2"] = {"last_seen": "2024-01-03T00:00:00"}
        self.db._data["ips"]["3.3.3.3"] = {"last_seen": "2024-01-02T00:00:00"}

        result = self.db.get_recent_activity(limit=2)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["ip"], "2.2.2.2")
        self.assertEqual(result[1]["ip"], "3.3.3.3")

    def test_get_stats(self):
        """Should return statistics copy."""
        self.db.record_attempt("1.1.1.1", "sshd")
        self.db.record_ban("2.2.2.2", "sshd")

        result = self.db.get_stats()

        self.assertEqual(result["total_ips"], 2)
        self.assertEqual(result["total_attempts"], 1)
        self.assertEqual(result["total_bans"], 1)


class TestAnalytics(unittest.TestCase):
    """Tests for analytics methods."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db.json"
        self.db = AttacksDatabase(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_recalculate_stats(self):
        """Should recalculate aggregate statistics."""
        self.db.record_attempt("1.1.1.1", "sshd")
        self.db.record_attempt("1.1.1.1", "sshd")
        self.db.record_ban("2.2.2.2", "sshd")
        self.db.set_geo("1.1.1.1", "US", "Cloudflare")
        self.db.set_geo("2.2.2.2", "US", "Cloudflare")

        self.db.recalculate_stats()

        stats = self.db.get_stats()
        self.assertEqual(stats["total_ips"], 2)
        self.assertEqual(stats["total_attempts"], 2)
        self.assertEqual(stats["total_bans"], 1)
        self.assertEqual(stats["active_bans"], 1)
        self.assertEqual(stats["top_country"], "US")

    def test_calculate_danger_score_unknown_ip(self):
        """Should return 0 for unknown IP."""
        result = self.db.calculate_danger_score("unknown")
        self.assertEqual(result, 0)

    def test_calculate_danger_score_factors(self):
        """Should calculate score based on multiple factors."""
        # Create IP with attempts and bans
        self.db.record_attempt("1.1.1.1", "sshd")
        for _ in range(50):
            self.db.record_attempt("1.1.1.1", "sshd")
        self.db.record_ban("1.1.1.1", "sshd")
        self.db.record_attempt("1.1.1.1", "recidive")  # Recidive involvement

        score = self.db.calculate_danger_score("1.1.1.1")

        # Should have points for: attempts, bans, recidive, recent activity, active ban
        self.assertGreater(score, 50)
        self.assertLessEqual(score, 100)

    def test_recalculate_danger_scores_all(self):
        """Should recalculate scores for all IPs."""
        self.db.record_ban("1.1.1.1", "sshd")
        self.db.record_ban("2.2.2.2", "sshd")

        self.db.recalculate_danger_scores()

        self.assertIsNotNone(self.db.get_ip("1.1.1.1")["analysis"]["last_analysis"])
        self.assertIsNotNone(self.db.get_ip("2.2.2.2")["analysis"]["last_analysis"])


class TestLogPositionTracking(unittest.TestCase):
    """Tests for log position tracking."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db.json"
        self.db = AttacksDatabase(self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_get_log_position_returns_none_for_unknown(self):
        """Should return None for unknown log file."""
        result = self.db.get_log_position("/var/log/unknown.log")
        self.assertIsNone(result)

    def test_set_and_get_log_position(self):
        """Should store and retrieve log position."""
        self.db.set_log_position("/var/log/fail2ban.log", 1000, inode=12345)

        result = self.db.get_log_position("/var/log/fail2ban.log")

        self.assertEqual(result["position"], 1000)
        self.assertEqual(result["inode"], 12345)


class TestThreadSafety(unittest.TestCase):
    """Tests for thread safety."""

    def test_concurrent_writes(self):
        """Should handle concurrent writes safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db.json"
            db = AttacksDatabase(db_path)

            def worker(ip_prefix: str):
                for i in range(50):
                    db.record_attempt(f"{ip_prefix}.{i}", "sshd")

            threads = [
                threading.Thread(target=worker, args=(f"10.{t}",))
                for t in range(4)
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Should have 200 IPs (4 threads × 50 IPs each)
            self.assertEqual(db._data["stats"]["total_ips"], 200)


if __name__ == '__main__':
    unittest.main()
