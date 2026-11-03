"""Tests de bascule : no-op sans écriture, une seule écriture,
échec d'écriture, réponse perdue, état non confirmé, délai global."""
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
from fake_router import FakeSession, default_state, load_script, run_action

mod = load_script()


class TestNoop(unittest.TestCase):
    def test_off_when_off_writes_nothing(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="0")])
        code, result = run_action(mod, "off", session)
        self.assertEqual(code, 2)
        self.assertTrue(result["success"])
        self.assertFalse(result["changed"])
        self.assertEqual(result["status"], "allowed")
        self.assertEqual(session.write_count(), 0)

    def test_on_when_on_writes_nothing(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="1")])
        code, result = run_action(mod, "on", session)
        self.assertEqual(code, 2)
        self.assertTrue(result["success"])
        self.assertFalse(result["changed"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(session.write_count(), 0)


class TestToggleWritesOnce(unittest.TestCase):
    def test_toggle_off_to_on_single_write(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="0"),
                                      default_state(UrlFilterEnable="1")])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 0)
        self.assertTrue(result["success"])
        self.assertTrue(result["changed"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["previous_status"], "allowed")
        self.assertEqual(session.write_count(), 1)
        body = session.writes[0]
        self.assertIn("UrlFilterEnable=1", body)
        self.assertIn("UrlFilterTarget=0", body)
        self.assertIn("MacFilterEnable=0", body)
        self.assertIn("IF_ACTION=Apply", body)

    def test_toggle_on_to_off_single_write(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="1"),
                                      default_state(UrlFilterEnable="0")])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "allowed")
        self.assertEqual(session.write_count(), 1)
        self.assertIn("UrlFilterEnable=0", session.writes[0])

    def test_on_forces_on(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="0"),
                                      default_state(UrlFilterEnable="1")])
        code, result = run_action(mod, "on", session)
        self.assertEqual(code, 0)
        self.assertEqual(session.write_count(), 1)


class TestWriteFailures(unittest.TestCase):
    def test_write_refused_is_exit_5(self):
        session = FakeSession(
            states=[default_state(UrlFilterEnable="0"),
                    default_state(UrlFilterEnable="0")],
            write_response="FAIL")
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 5)
        self.assertEqual(result["error"], "WRITE_FAILED")
        self.assertFalse(result["success"])

    def test_write_response_lost_is_exit_6(self):
        import requests
        session = FakeSession(states=[default_state(UrlFilterEnable="0")],
                              raise_on={"write":
                                        requests.ConnectionError("reset")})
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 6)
        self.assertEqual(result["error"], "STATE_NOT_CONFIRMED")

    def test_http_success_but_state_unchanged_is_exit_6(self):
        # Le routeur répond SUCC mais la relecture montre l'ancien état.
        session = FakeSession(states=[default_state(UrlFilterEnable="0"),
                                      default_state(UrlFilterEnable="0")])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 6)
        self.assertEqual(result["error"], "STATE_NOT_CONFIRMED")


class TestDeadline(unittest.TestCase):
    def test_budget_uses_min_of_default_and_remaining(self):
        deadline = mod.Deadline(120)
        self.assertEqual(deadline.budget(15), 15)
        self.assertGreater(deadline.remaining(), 0)

    def test_expired_deadline_raises(self):
        deadline = mod.Deadline(120)
        deadline.end = time.monotonic() - 1  # déjà expiré
        with self.assertRaises(mod.OperationTimeout):
            deadline.check()
        with self.assertRaises(mod.OperationTimeout):
            deadline.budget(15)


class TestAlreadyRunning(unittest.TestCase):
    def test_second_execution_is_exit_7(self):
        lock = mod.ExecutionLock(mod.lock_path())
        lock.__enter__()
        try:
            session = FakeSession()
            code, result = run_action(mod, "toggle", session)
            self.assertEqual(code, 7)
            self.assertEqual(result["error"], "ALREADY_RUNNING")
            self.assertEqual(session.gets, [])  # routeur jamais contacté
        finally:
            lock.__exit__(None, None, None)


if __name__ == "__main__":
    unittest.main()
