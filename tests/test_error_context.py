"""Tests du contexte d'erreur : previous_status après écriture,
code 9 ROUTER_ERROR, flag --version, format du rnd secrets."""
import io
import re
import sys
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

import requests

sys.path.insert(0, os.path.dirname(__file__))
from fake_router import (FakeSession, TEST_CONFIG, default_state,
                         fake_create_connection, failing_create_connection,
                         load_script, run_action)

mod = load_script()


class HttpErrorSession(FakeSession):
    """Échoue avec HTTPError sur le premier GET login_entry."""

    def get(self, url, **kwargs):
        if "login_entry" in url and "login_token" not in url:
            raise requests.HTTPError("500 Server Error")
        return super().get(url, **kwargs)


class VerifyTimeoutSession(FakeSession):
    """Timeout sur la 2e lecture d'état (la relecture de vérification)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state_gets = 0

    def get(self, url, **kwargs):
        if "firewall_filterglobal_lua.lua" in url:
            self._state_gets += 1
            if self._state_gets == 2:
                raise requests.Timeout("verify timed out")
        return super().get(url, **kwargs)


class TestPreviousStatusAfterWrite(unittest.TestCase):
    def test_lost_write_response_keeps_previous_status(self):
        session = FakeSession(
            states=[default_state(UrlFilterEnable="0")],
            raise_on={"write": requests.ConnectionError("boom")})
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 6)
        self.assertEqual(result["error"], "STATE_NOT_CONFIRMED")
        self.assertEqual(result["previous_status"], "allowed")

    def test_write_timeout_keeps_previous_status(self):
        session = FakeSession(
            states=[default_state(UrlFilterEnable="0")],
            raise_on={"write": requests.Timeout("write timed out")})
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 6)
        self.assertEqual(result["error"], "STATE_NOT_CONFIRMED")
        self.assertEqual(result["previous_status"], "allowed")

    def test_verify_timeout_keeps_previous_status(self):
        session = VerifyTimeoutSession(
            states=[default_state(UrlFilterEnable="0")])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 6)
        self.assertEqual(result["error"], "STATE_NOT_CONFIRMED")
        self.assertEqual(result["previous_status"], "allowed")

    def test_verify_mismatch_keeps_previous_status(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="0"),
                                      default_state(UrlFilterEnable="0")])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 6)
        self.assertEqual(result["error"], "STATE_NOT_CONFIRMED")
        self.assertEqual(result["previous_status"], "allowed")

    def test_pre_read_failure_keeps_previous_null(self):
        session = FakeSession()
        code, result = run_action(mod, "toggle", session, reachable=False)
        self.assertEqual(code, 3)
        self.assertEqual(result["error"], "ROUTER_UNREACHABLE")
        self.assertIsNone(result["previous_status"])
        self.assertIn("hors du réseau domestique", result["message"])


class TestRouterErrorCode9(unittest.TestCase):
    def test_login_garbage_response_is_code_9(self):
        session = FakeSession()
        session.login_response = None  # json() lève ValueError
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 9)
        self.assertEqual(result["error"], "ROUTER_ERROR")
        self.assertIsNone(result["previous_status"])

    def test_http_error_is_code_9(self):
        session = HttpErrorSession()
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 9)
        self.assertEqual(result["error"], "ROUTER_ERROR")

    def test_pure_unreachable_stays_code_3(self):
        session = FakeSession()
        code, result = run_action(mod, "toggle", session, reachable=False)
        self.assertEqual(code, 3)
        self.assertEqual(result["error"], "ROUTER_UNREACHABLE")


class TestVersionFlag(unittest.TestCase):
    def test_version_prints_and_exits_zero_without_router(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mod.main(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue().strip(), "2.0.0")
        self.assertEqual(mod.__version__, "2.0.0")

    def test_version_and_help_work_without_requests(self):
        # --version et --help sont traités avant le test de dépendance.
        with mock.patch.object(mod, "requests", None):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = mod.main(["--version"])
            self.assertEqual(code, 0)
            self.assertEqual(buf.getvalue().strip(), "2.0.0")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = mod.main(["--help"])
            self.assertEqual(code, 0)
            self.assertIn("Usage", buf.getvalue())

    def test_normal_action_without_requests_is_exit_8(self):
        with mock.patch.object(mod, "requests", None):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = mod.main(["toggle"])
            self.assertEqual(code, 8)
            self.assertIn("MISSING_DEPENDENCY", buf.getvalue())


class TestSecretsRnd(unittest.TestCase):
    def test_login_token_rnd_is_16_lowercase_hex(self):
        session = FakeSession()
        run_action(mod, "status", session)
        urls = [u for u in session.gets if "login_token" in u]
        self.assertEqual(len(urls), 1)
        rnd = urls[0].split("_=")[-1]
        self.assertRegex(rnd, r"^[0-9a-f]{16}$")


if __name__ == "__main__":
    unittest.main()
