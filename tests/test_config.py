"""Tests des permissions de config.json (refus si droits trop ouverts)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
from fake_router import (FakeSession, TEST_CONFIG, default_state,
                         fake_create_connection, load_script, run_action)

mod = load_script()


def write_config(directory, password="test-password", mode=0o600):
    """Crée un config.json temporaire avec le mode demandé."""
    path = os.path.join(directory, "config.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"router_ip": "192.168.11.1", "username": "user",
                   "password": password}, handle)
    os.chmod(path, mode)
    return path


@unittest.skipUnless(os.name == "posix",
                         "les permissions Unix ne s'appliquent pas hors POSIX")
class TestConfigPermissions(unittest.TestCase):
    def test_mode_600_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_config(directory, mode=0o600)
            with mock.patch.object(mod, "config_path",
                                   return_value=path):
                cfg = mod.load_config()
        self.assertEqual(cfg["password"], "test-password")

    def test_mode_400_loads(self):
        # Seul le test mode & 0o077 compte : 400 (lecture propriétaire
        # seule) est accepté, il ne faut pas exiger exactement 600.
        with tempfile.TemporaryDirectory() as directory:
            path = write_config(directory, mode=0o400)
            with mock.patch.object(mod, "config_path",
                                   return_value=path):
                cfg = mod.load_config()
        self.assertEqual(cfg["password"], "test-password")

    def test_mode_640_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_config(directory, mode=0o640)
            with mock.patch.object(mod, "config_path",
                                   return_value=path):
                with self.assertRaises(mod.ConfigError) as caught:
                    mod.load_config()
        self.assertEqual(caught.exception.error, "CONFIG_PERMISSIONS")
        self.assertIn("chmod 600", str(caught.exception))

    def test_mode_644_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_config(directory, mode=0o644)
            with mock.patch.object(mod, "config_path",
                                   return_value=path):
                with self.assertRaises(mod.ConfigError) as caught:
                    mod.load_config()
        self.assertEqual(caught.exception.error, "CONFIG_PERMISSIONS")

    def test_permissions_refused_maps_to_exit_8(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_config(directory, mode=0o644)
            session = FakeSession()
            with mock.patch.object(mod, "config_path",
                                   return_value=path), \
                mock.patch.object(mod.requests, "Session",
                                  lambda *a, **k: session), \
                mock.patch.object(mod.socket, "create_connection",
                                  fake_create_connection):
                code, result = mod.execute("toggle")
        self.assertEqual(code, 8)
        self.assertEqual(result["error"], "CONFIG_PERMISSIONS")
        self.assertEqual(session.write_count(), 0)

    def test_empty_password_in_file_does_not_override(self):
        # Une valeur vide dans config.json ne remplace pas la constante.
        with tempfile.TemporaryDirectory() as directory:
            path = write_config(directory, password="", mode=0o600)
            with mock.patch.object(mod, "config_path",
                                   return_value=path):
                with self.assertRaises(mod.ConfigError) as caught:
                    mod.load_config()
        self.assertEqual(caught.exception.error, "PASSWORD_NOT_CONFIGURED")


class TestConfigPermissionsSkippedOffPosix(unittest.TestCase):
    def test_check_skipped_when_not_posix(self):
        # Hors POSIX, les bits de mode ne portent pas la même
        # signification : le contrôle est sauté, même pour un 644.
        with tempfile.TemporaryDirectory() as directory:
            path = write_config(directory, mode=0o644)
            with mock.patch.object(mod, "config_path",
                                   return_value=path), \
                mock.patch.object(mod.os, "name", "nt"):
                cfg = mod.load_config()
        self.assertEqual(cfg["password"], "test-password")


if __name__ == "__main__":
    unittest.main()
