"""Tests de lecture d'état : parsing XML, erreurs, mapping blocked/allowed,
détection de la liste blanche (abandon sans écriture)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
from fake_router import (FakeResponse, FakeSession, default_state,
                         load_script, run_action)

mod = load_script()


class TestStateParsing(unittest.TestCase):
    def _session(self, **kwargs):
        return FakeSession(**kwargs)

    def test_parse_state(self):
        session = self._session(states=[default_state(
            UrlFilterEnable="1", UrlFilterTarget="0",
            MacFilterEnable="1", MacFilterTarget="0")])
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            etat = mod.lire_etat_filtre(session, "http://192.168.11.1")
        self.assertEqual(etat["UrlFilterEnable"], "1")
        self.assertEqual(etat["UrlFilterTarget"], "0")
        self.assertEqual(etat["MacFilterEnable"], "1")
        self.assertEqual(etat["MacFilterTarget"], "0")

    def test_parse_bad_if_errorstr(self):
        session = self._session()
        session.get = lambda url, **kw: FakeResponse(
            text="<root><IF_ERRORSTR>FAIL</IF_ERRORSTR></root>")
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            with self.assertRaises(mod.StateReadError):
                mod.lire_etat_filtre(session, "http://192.168.11.1")

    def test_parse_malformed_xml(self):
        session = self._session()
        session.get = lambda url, **kw: FakeResponse(text="ceci n'est pas du XML")
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            with self.assertRaises(mod.StateReadError):
                mod.lire_etat_filtre(session, "http://192.168.11.1")


class TestStatusMapping(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(mod.status_label("1"), "blocked")
        self.assertEqual(mod.status_label("0"), "allowed")

    def test_status_command_reads_only(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="1")])
        code, result = run_action(mod, "status", session)
        self.assertEqual(code, 0)
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["requested_action"], "status")
        self.assertTrue(result["verified"])
        self.assertEqual(session.write_count(), 0)


class TestWhitelistDetection(unittest.TestCase):
    def test_whitelist_aborts_without_write(self):
        # UrlFilterTarget "1" = liste blanche : abandon de sécurité.
        session = FakeSession(states=[default_state(UrlFilterTarget="1")])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 8)
        self.assertEqual(result["error"], "WHITELIST_DETECTED")
        self.assertFalse(result["success"])
        self.assertEqual(session.write_count(), 0)

    def test_blacklist_passes_guard(self):
        session = FakeSession(states=[default_state(UrlFilterTarget="0")])
        code, result = run_action(mod, "status", session)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "allowed")


if __name__ == "__main__":
    unittest.main()
