"""Tests du contrat Tasker : formes JSON succès/échec, cohérence avec les
codes de sortie, format texte humain, commande status, sortie de main()."""
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
from fake_router import (FakeSession, TEST_CONFIG, default_state,
                         fake_create_connection, load_script, run_action)

mod = load_script()


def run_main(mod, argv, session, reachable=True):
    """Appelle mod.main(argv) avec les dépendances mockées, stdout capturé."""
    from fake_router import failing_create_connection
    create = fake_create_connection if reachable else failing_create_connection
    buf = io.StringIO()
    with mock.patch.object(mod, "load_config",
                           return_value=dict(TEST_CONFIG)), \
        mock.patch.object(mod.requests, "Session",
                          lambda *a, **k: session), \
        mock.patch.object(mod.socket, "create_connection", create), \
        redirect_stdout(buf):
        code = mod.main(argv)
    return code, buf.getvalue()


class TestJsonContract(unittest.TestCase):
    def test_success_json_shape(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="0"),
                                      default_state(UrlFilterEnable="1")])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 0)
        self.assertEqual(result, {
            "success": True,
            "status": "blocked",
            "previous_status": "allowed",
            "requested_action": "toggle",
            "verified": True,
            "changed": True,
            "message": result["message"],
        })
        self.assertNotIn("error", result)

    def test_failure_json_shape(self):
        session = FakeSession()
        code, result = run_action(mod, "toggle", session, reachable=False)
        self.assertEqual(code, 3)
        self.assertEqual(result["success"], False)
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["previous_status"])
        self.assertEqual(result["verified"], False)
        self.assertEqual(result["error"], "ROUTER_UNREACHABLE")
        self.assertNotIn("changed", result)

    def test_noop_json_shape(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="0")])
        code, result = run_action(mod, "off", session)
        self.assertEqual(code, 2)
        self.assertTrue(result["success"])
        self.assertTrue(result["verified"])
        self.assertFalse(result["changed"])
        self.assertEqual(result["status"], "allowed")
        self.assertEqual(result["previous_status"], "allowed")

    def test_status_json_shape(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="1")])
        code, result = run_action(mod, "status", session)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["previous_status"])
        self.assertEqual(result["requested_action"], "status")
        self.assertFalse(result["changed"])

    def test_main_prints_single_line_json(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="0"),
                                      default_state(UrlFilterEnable="1")])
        code, out = run_main(mod, ["toggle"], session)
        self.assertEqual(code, 0)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["status"], "blocked")


class TestTextFormat(unittest.TestCase):
    def test_text_output_is_not_json(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="0"),
                                      default_state(UrlFilterEnable="1")])
        code, out = run_main(mod, ["toggle", "--format", "text"], session)
        self.assertEqual(code, 0)
        self.assertNotIn("{", out)
        self.assertIn("ACTIVÉ", out)
        self.assertIn("succès", out)

    def test_text_error_output(self):
        session = FakeSession()
        code, out = run_main(mod, ["toggle", "--format", "text"], session,
                             reachable=False)
        self.assertEqual(code, 3)
        self.assertIn("ROUTER_UNREACHABLE", out)
        self.assertNotIn("{", out)

    def test_invalid_format_is_exit_8(self):
        session = FakeSession()
        code, out = run_main(mod, ["toggle", "--format", "yaml"], session)
        self.assertEqual(code, 8)
        parsed = json.loads(out.strip())
        self.assertEqual(parsed["error"], "INVALID_USAGE")

    def test_invalid_action_is_exit_8(self):
        session = FakeSession()
        code, out = run_main(mod, ["nimporte-quoi"], session)
        self.assertEqual(code, 8)
        parsed = json.loads(out.strip())
        self.assertEqual(parsed["error"], "INVALID_USAGE")

    def test_help_exits_zero(self):
        session = FakeSession()
        code, out = run_main(mod, ["--help"], session)
        self.assertEqual(code, 0)
        self.assertIn("Usage", out)


if __name__ == "__main__":
    unittest.main()
