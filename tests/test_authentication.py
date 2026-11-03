"""Tests d'authentification : login ok / refusé / verrouillé / token manquant,
hash du mot de passe, erreurs HTTP, configuration du mot de passe."""
import hashlib
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
from fake_router import (FakeSession, TEST_CONFIG, default_state,
                         failing_create_connection, fake_create_connection,
                         load_script, run_action)

mod = load_script()


class TestLogin(unittest.TestCase):
    def _session(self, **kwargs):
        return FakeSession(**kwargs)

    def test_login_success_returns_token(self):
        session = self._session()
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            token = mod.zte_login(session, "test-password",
                                  "http://192.168.11.1", "user")
        self.assertEqual(token, "TOKEN123")

    def test_login_sends_sha256_password_plus_token(self):
        session = self._session()
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            mod.zte_login(session, "test-password",
                          "http://192.168.11.1", "user")
        login_posts = [data for url, data in session.posts
                       if "login_entry" in url]
        self.assertEqual(len(login_posts), 1)
        expected = hashlib.sha256(
            "test-passwordLOGINTOKEN".encode("utf-8")).hexdigest()
        self.assertEqual(login_posts[0]["Password"], expected)
        self.assertEqual(login_posts[0]["Username"], "user")
        self.assertEqual(login_posts[0]["_sessionTOKEN"], "TOKEN123")

    def test_login_refused(self):
        session = self._session(login_response={"loginErrMsg": "bad password"})
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            with self.assertRaises(mod.AuthError):
                mod.zte_login(session, "mauvais-mot-de-passe",
                              "http://192.168.11.1", "user")

    def test_login_router_locked(self):
        session = self._session(
            login_entry={"sess_token": "TOKEN123", "lockingTime": 300,
                         "loginErrMsg": "too many attempts"})
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            with self.assertRaises(mod.AuthError) as ctx:
                mod.zte_login(session, "test-password",
                              "http://192.168.11.1", "user")
        self.assertIn("verrouillé", str(ctx.exception))

    def test_login_missing_session_token(self):
        session = self._session(login_entry={"lockingTime": 0})
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            with self.assertRaises(mod.AuthError):
                mod.zte_login(session, "test-password",
                              "http://192.168.11.1", "user")

    def test_login_missing_login_token(self):
        session = self._session(token_xml="<root></root>")
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            with self.assertRaises(mod.AuthError):
                mod.zte_login(session, "test-password",
                              "http://192.168.11.1", "user")

    def test_login_http_error_propagates(self):
        import requests
        session = self._session()
        session.get = mock.Mock(
            side_effect=requests.HTTPError("500 Server Error"))
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            with self.assertRaises(requests.HTTPError):
                mod.zte_login(session, "test-password",
                              "http://192.168.11.1", "user")

    def test_auth_failure_maps_to_exit_4(self):
        session = self._session(login_response={"loginErrMsg": "bad password"})
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 4)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "AUTH_FAILED")
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(session.write_count(), 0)

    def test_unreachable_maps_to_exit_3(self):
        session = self._session()
        code, result = run_action(mod, "toggle", session, reachable=False)
        self.assertEqual(code, 3)
        self.assertEqual(result["error"], "ROUTER_UNREACHABLE")
        self.assertEqual(session.write_count(), 0)


class TestPasswordConfig(unittest.TestCase):
    def test_missing_password_is_exit_8(self):
        # La vraie validation de load_config (sans fichier, PASSWORD vide).
        with mock.patch.object(mod, "config_path",
                               return_value="/nonexistent/config.json"), \
            mock.patch.object(mod, "PASSWORD", ""):
            with self.assertRaises(mod.ConfigError) as ctx:
                mod.load_config()
            self.assertEqual(ctx.exception.error, "PASSWORD_NOT_CONFIGURED")
        # Et via execute : le routeur n'est jamais contacté.
        session = FakeSession()
        with mock.patch.object(mod, "load_config",
                               side_effect=mod.ConfigError(
                                   "mot de passe non configuré",
                                   "PASSWORD_NOT_CONFIGURED")), \
            mock.patch.object(mod.requests, "Session",
                              lambda *a, **k: session), \
            mock.patch.object(mod.socket, "create_connection",
                              fake_create_connection):
            code, result = mod.execute("toggle")
        self.assertEqual(code, 8)
        self.assertEqual(result["error"], "PASSWORD_NOT_CONFIGURED")
        self.assertEqual(session.gets, [])  # routeur jamais contacté

    def test_invalid_config_json_is_exit_8(self):
        session = FakeSession()
        with mock.patch.object(mod, "load_config",
                               side_effect=mod.ConfigError(
                                   "config illisible", "INVALID_CONFIG")), \
            mock.patch.object(mod.requests, "Session",
                              lambda *a, **k: session), \
            mock.patch.object(mod.socket, "create_connection",
                              fake_create_connection):
            code, result = mod.execute("toggle")
        self.assertEqual(code, 8)
        self.assertEqual(result["error"], "INVALID_CONFIG")


if __name__ == "__main__":
    unittest.main()
