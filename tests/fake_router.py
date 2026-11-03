"""Routeur ZTE F6600P simulé pour les tests (aucun routeur physique requis).

Fournit un faux requests.Session qui répond comme le routeur réel :
login, lecture d'état XML, écriture, ainsi qu'un chargeur du script à tester.
"""
import importlib.util
import os
from unittest import mock


def default_state(**overrides):
    """État standard : filtre désactivé, liste noire, filtre MAC désactivé."""
    state = {
        "UrlFilterEnable": "0",
        "UrlFilterTarget": "0",
        "MacFilterEnable": "0",
        "MacFilterTarget": "0",
    }
    state.update(overrides)
    return state


def state_xml(state):
    parts = ["<root><IF_ERRORSTR>SUCC</IF_ERRORSTR><Instance>"]
    for name, value in state.items():
        parts.append("<ParaName>%s</ParaName><ParaValue>%s</ParaValue>"
                     % (name, value))
    parts.append("</Instance></root>")
    return "".join(parts)


class FakeResponse:
    def __init__(self, text="", json_data=None, raise_http=None):
        self.text = text
        self.content = text.encode("utf-8")
        self._json = json_data
        self._raise_http = raise_http

    def json(self):
        if self._json is None:
            raise ValueError("pas de JSON dans cette réponse")
        return self._json

    def raise_for_status(self):
        if self._raise_http is not None:
            raise self._raise_http


class FakeSession:
    """Imite requests.Session face au script (GET/POST + headers)."""

    def __init__(self, states=None, login_entry=None, login_response=None,
                 write_response="SUCC", token_xml=None, raise_on=None):
        self.headers = {}
        self.states = list(states or [default_state()])
        self.state_index = 0
        self.writes = []  # bodies POSTés sur l'endpoint d'écriture
        self.posts = []   # (url, data) de tous les POST
        self.gets = []    # urls de tous les GET
        self.login_entry = login_entry or {"sess_token": "TOKEN123",
                                           "lockingTime": 0}
        self.login_response = login_response \
            if login_response is not None else {}
        self.write_response = write_response
        self.token_xml = token_xml or "<login_token>LOGINTOKEN</login_token>"
        self.raise_on = raise_on or {}  # ex. {"write": ConnectionError()}

    def get(self, url, **kwargs):
        self.gets.append(url)
        if "login_token" in url:
            return FakeResponse(text=self.token_xml)
        if "logout" in url:
            return FakeResponse(text="OK")
        if "menuView" in url:
            return FakeResponse(text="OK")
        if "firewall_filterglobal_lua.lua" in url:
            state = self.states[min(self.state_index, len(self.states) - 1)]
            self.state_index += 1
            return FakeResponse(text=state_xml(state))
        if "login_entry" in url:
            return FakeResponse(json_data=self.login_entry)
        return FakeResponse(text="OK")

    def post(self, url, data=None, headers=None, **kwargs):
        self.posts.append((url, data))
        if "firewall_filterglobal_lua.lua" in url:
            if "write" in self.raise_on:
                raise self.raise_on["write"]
            self.writes.append(data)
            return FakeResponse(
                text="<root><IF_ERRORSTR>%s</IF_ERRORSTR></root>"
                     % self.write_response)
        if "login_entry" in url:
            return FakeResponse(json_data=self.login_response)
        return FakeResponse(text="OK")

    def write_count(self):
        return len(self.writes)


class FakeSocket:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_create_connection(address, timeout=None):
    return FakeSocket()


def failing_create_connection(address, timeout=None):
    raise OSError("Network is unreachable")


def load_script():
    """Charge toggle_filtre_url.py comme module, sans l'exécuter."""
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                        "toggle_filtre_url.py"))
    spec = importlib.util.spec_from_file_location("toggle_filtre_url_v2",
                                                  path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TEST_CONFIG = {"router_ip": "192.168.11.1", "username": "user",
               "password": "test-password"}


def run_action(mod, action, session, config=None, reachable=True):
    """Exécute mod.execute(action) avec session/socket/config mockés."""
    create = fake_create_connection if reachable else failing_create_connection
    with mock.patch.object(mod, "load_config",
                           return_value=config or dict(TEST_CONFIG)), \
        mock.patch.object(mod.requests, "Session",
                          lambda *a, **k: session), \
        mock.patch.object(mod.socket, "create_connection", create):
        return mod.execute(action)
