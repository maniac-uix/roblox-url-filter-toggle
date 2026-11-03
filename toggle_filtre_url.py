#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BASCULE ON/OFF du "Filtre d'URL" — ZTE F6600P (Orange Maroc Livebox WiFi 6).
Version 2 : fiabilisée (audit 2026-11-04, phases 1 et 2).

Ce que fait ce script :
  - se connecte au routeur (flux validé par les sondes),
  - lit l'état actuel du filtre d'URL (Activé/Désactivé) et du mode (Liste noire),
  - bascule le Filtre d'URL vers l'état demandé, en UNE SEULE écriture,
  - RELIT l'état pour confirmer que la bascule a bien eu lieu,
    y compris que les paramètres protégés (mode, filtre MAC) sont inchangés.

Ce qu'il NE fait PAS :
  - il ne touche JAMAIS à la liste des URL (tes règles Roblox restent intactes),
  - il ne touche ni au filtre MAC, ni au mode (reste en Liste noire),
  - il n'affiche JAMAIS "succès" sans avoir vérifié le nouvel état,
  - il n'écrit RIEN si l'état demandé est déjà l'état actuel.

Sortie par défaut : un objet JSON sur une seule ligne (contrat Tasker),
cohérent avec le code de sortie. Option --format text pour un usage humain.

Utilisation :
  python toggle_filtre_url.py                # bascule (toggle, par défaut)
  python toggle_filtre_url.py on             # active le filtre (Roblox bloqué)
  python toggle_filtre_url.py off            # désactive le filtre (Roblox autorisé)
  python toggle_filtre_url.py toggle         # bascule
  python toggle_filtre_url.py status         # lecture seule, aucune écriture
  python toggle_filtre_url.py toggle --format text

Configuration (par ordre de priorité) :
  1. fichier config.json à côté du script (router_ip, username, password),
  2. constante PASSWORD ci-dessous (vide par défaut, compatibilité v1).
  Sans mot de passe : erreur PASSWORD_NOT_CONFIGURED, code 8.

Codes de sortie :
  0 succès (changé + vérifié)      4 authentification refusée
  2 déjà dans l'état demandé       5 écriture refusée / échouée
  3 routeur injoignable            6 état final non confirmé
  7 exécution déjà en cours        8 usage / configuration invalide
"""

import base64
import hashlib
import json
import os
import random
import re
import socket
import sys
import tempfile
import time
import warnings
import xml.etree.ElementTree as ET

warnings.filterwarnings("ignore")

try:
    import requests
except ImportError:
    requests = None

try:
    import fcntl
except ImportError:  # pragma: no cover - plateformes non Unix
    fcntl = None


# ---------------------------------------------------------------- paramètres
ROUTER_IP = "192.168.11.1"
USERNAME = "user"
# Mot de passe admin : laisser vide ("") et utiliser config.json.
# Ne JAMAIS renseigner un vrai mot de passe dans une copie destinée à Git.
PASSWORD = ""
# Action par défaut si aucun argument : "toggle" (bascule).
MODE = "toggle"

GLOBAL_TIMEOUT = 120  # secondes, pour toute l'opération
TCP_TIMEOUT = 3       # secondes, pour la pré-vérification de joignabilité
LOCK_FILENAME = "roblox_toggle.lock"
PROTECTED_PARAMS = ("UrlFilterTarget", "MacFilterEnable", "MacFilterTarget")

EXIT_OK = 0
EXIT_ALREADY = 2
EXIT_UNREACHABLE = 3
EXIT_AUTH = 4
EXIT_WRITE = 5
EXIT_UNCONFIRMED = 6
EXIT_RUNNING = 7
EXIT_USAGE = 8

# Clé publique RSA 4096 bits du F6600P (publique, pas secrète).
# Vérifiée : identique à celle du projet open-source juacas/zte_tracker
# (modèle F6600P confirmé).
RSA_N_HEX = (
    "c25a3fbd9067489d8cc89d1d6cd7300efccfa8137e3bf04fbcb5fddc62095526"
    "66aae2470fd5fa5e7e9561e33d9912b38c46d73e5bfbdc38ff8238ed363f634e"
    "ad905725b649de19918f5ede1d402c20827e46e39e64aa79dcab72f5eb893796"
    "f89eb98e10637ba95325b69f982e6a6c6888b63b7439e3a44fe55be12ee160f4"
    "9622379860187eed8fdf836e51b766be4600bc75a86f277b6d0752c75c00eba0"
    "29baabb1be9696d1025a42f238dcd2b65d4b473a1dc068620cd6f2fc638f67d3"
    "b85cb7099653ae93f24effc2f0ae818634e78d17baa1c80557243444861fc768"
    "7148972e6ae479ececdf333960150bf74405e0b8366db955052cedac022c0b10"
    "ba61dc071fcbd121e7c48772cc19bec3925d8d0935bd1779133d831a67b4b45f"
    "33a4c1edff6162d6130f0e6829dc8d058fa79c46bf2290548e77460eb4acdd9e"
    "01c516d870913090a41992fc3fe53a5061b903eac4d15529593da5d28de0a5d2"
    "1b0b0adb6ac09a9165c8db597ac8341605c3c3d8135e17afd042c8f82aa1c750"
    "87b160bdab15806eaee662d1d4f059a3810517f2dd634caf306e6b97d7a0064d"
    "570ff50c6b2851b66490114cd8b7778458b05ba8907a31b549db281cbf910b45"
    "e0d8d12597c353c811b1de3f9d40fccc81ea4c12819c1da105b726268f9c61cc"
    "684d0da9f0183cd88624b32c9af4ffacd508ffc892096f96bd2cf1f6d072531b"
)
RSA_E = 65537


# ------------------------------------------------------------------ erreurs
class ToggleError(Exception):
    """Erreur structurée : code de sortie + code machine + message."""
    exit_code = EXIT_UNCONFIRMED
    error = "INTERNAL_ERROR"

    def __init__(self, message, error=None):
        super().__init__(message)
        if error is not None:
            self.error = error


class RouterUnreachable(ToggleError):
    exit_code = EXIT_UNREACHABLE
    error = "ROUTER_UNREACHABLE"


class RouterError(ToggleError):
    exit_code = EXIT_UNREACHABLE
    error = "ROUTER_ERROR"


class AuthError(ToggleError):
    exit_code = EXIT_AUTH
    error = "AUTH_FAILED"


class WriteError(ToggleError):
    exit_code = EXIT_WRITE
    error = "WRITE_FAILED"


class StateReadError(ToggleError):
    exit_code = EXIT_UNCONFIRMED
    error = "STATE_READ_FAILED"


class StateNotConfirmed(ToggleError):
    exit_code = EXIT_UNCONFIRMED
    error = "STATE_NOT_CONFIRMED"


class ProtectedChanged(ToggleError):
    exit_code = EXIT_UNCONFIRMED
    error = "PROTECTED_PARAMS_CHANGED"


class AlreadyRunning(ToggleError):
    exit_code = EXIT_RUNNING
    error = "ALREADY_RUNNING"


class UsageError(ToggleError):
    exit_code = EXIT_USAGE
    error = "INVALID_USAGE"


class ConfigError(ToggleError):
    exit_code = EXIT_USAGE
    error = "INVALID_CONFIG"


class OperationTimeout(ToggleError):
    # Code décidé par l'appelant selon la phase (3 avant écriture, 6 après).
    exit_code = EXIT_UNCONFIRMED
    error = "TIMEOUT"


# ------------------------------------------------------------------- délai
class Deadline:
    """Délai global : chaque appel HTTP consomme le budget restant."""

    def __init__(self, seconds=GLOBAL_TIMEOUT):
        self.end = time.monotonic() + seconds

    def remaining(self):
        return self.end - time.monotonic()

    def check(self):
        if self.remaining() <= 0:
            raise OperationTimeout("délai global de %s s dépassé"
                                   % GLOBAL_TIMEOUT)

    def budget(self, default):
        """Timeout à passer à un appel HTTP : min(défaut, temps restant)."""
        self.check()
        return max(1, int(min(default, self.remaining())))


def _timeout(deadline, default):
    return deadline.budget(default) if deadline is not None else default


# ------------------------------------------------------------- crypto (RSA)
def rsa_pkcs1v15_encrypt(message: bytes) -> bytes:
    n = int(RSA_N_HEX, 16)
    k = (n.bit_length() + 7) // 8
    if len(message) > k - 11:
        raise ValueError("message trop long pour la clé RSA")
    padding_len = k - len(message) - 3
    import os
    padding = bytes(b for b in os.urandom(padding_len * 2) if b != 0)
    padding = padding[:padding_len]
    while len(padding) < padding_len:
        extra = bytes(b for b in os.urandom(padding_len) if b != 0)
        padding = (padding + extra)[:padding_len]
    em = b"\x00\x02" + padding + b"\x00" + message
    m = int.from_bytes(em, "big")
    c = pow(m, RSA_E, n)
    return c.to_bytes(k, "big")


def make_check_header(post_body: str) -> str:
    digest_hex = hashlib.sha256(post_body.encode("utf-8")).hexdigest()
    encrypted = rsa_pkcs1v15_encrypt(digest_hex.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


# ------------------------------------------------------------------- session
def new_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36",
        "Accept": "*/*",
    })
    return s


def zte_login(session, password, base, username, deadline=None):
    """Connexion validée par les sondes n°1 à n°5. Retourne sess_token.

    Lève AuthError si le routeur refuse l'authentification ou verrouille,
    RouterError si sa réponse est inexploitable. Les erreurs réseau
    (requests) remontent à l'appelant, qui les classe selon la phase.
    """
    r = session.get(base + "/?_type=loginData&_tag=login_entry",
                    timeout=_timeout(deadline, 15), verify=False)
    r.raise_for_status()
    info = r.json()
    if info.get("lockingTime", 0) not in (0, None):
        raise AuthError("routeur verrouillé %s s : %s"
                        % (info.get("lockingTime"), info.get("loginErrMsg")))
    sess_token = info.get("sess_token")
    if not sess_token:
        raise AuthError("pas de sess_token dans la réponse du routeur")

    rnd = "".join(random.choice("0123456789ABCDEF") for _ in range(16))
    r = session.get(base + "/?_type=loginData&_tag=login_token&_=" + rnd,
                    timeout=_timeout(deadline, 15), verify=False)
    r.raise_for_status()
    login_token = None
    try:
        root = ET.fromstring(r.content)
        if root.text and root.text.strip():
            login_token = root.text.strip()
        else:
            login_token = root.findtext("login_token")
    except Exception:
        pass
    if not login_token:
        m = re.search(r"<login_token>(.*?)</login_token>", r.text, re.S)
        if m:
            login_token = m.group(1).strip()
    if not login_token:
        raise AuthError("login_token introuvable dans la réponse du routeur")

    pwd_hash = hashlib.sha256(
        (password + login_token).encode("utf-8")).hexdigest()
    r = session.post(
        base + "/?_type=loginData&_tag=login_entry",
        data={"action": "login", "Password": pwd_hash,
              "Username": username, "_sessionTOKEN": sess_token},
        timeout=_timeout(deadline, 15), verify=False,
    )
    r.raise_for_status()
    try:
        res = r.json()
    except Exception:
        raise RouterError("réponse de connexion inattendue du routeur")
    if res.get("loginErrMsg"):
        raise AuthError("connexion refusée : %s" % res.get("loginErrMsg"))
    if res.get("lockingTime", 0) not in (0, None):
        raise AuthError("routeur verrouillé (%s s)." % res.get("lockingTime"))
    return sess_token


def zte_logout(session, base):
    try:
        session.get(base + "/?_type=loginData&_tag=logout", timeout=10,
                    verify=False)
    except Exception:
        pass


# ------------------------------------------------------------ filtre d'URL
def lire_etat_filtre(session, base, deadline=None):
    """Lit OBJ_FWBASE_ID. Retourne le dict des paramètres.

    Lève StateReadError si la réponse est inexploitable.
    """
    # Le routeur exige que la page (menuView) soit chargée avant de servir
    # ses données (menuData) : sans ça, il répond SessionTimeout.
    # (Séquence identique à la sonde n°5, qui fonctionnait.)
    session.get(
        base + "/?_type=menuView&_tag=filterCriteria&Menu3Location=0",
        timeout=_timeout(deadline, 25), verify=False)
    r = session.get(
        base + "/?_type=menuData&_tag=firewall_filterglobal_lua.lua",
        timeout=_timeout(deadline, 20), verify=False)
    r.raise_for_status()
    try:
        root = ET.fromstring(r.content)
    except Exception:
        raise StateReadError("réponse d'état inattendue du routeur")
    if (root.findtext("IF_ERRORSTR") or "") not in ("SUCC", "SUCCESS", "OK"):
        raise StateReadError("le routeur a refusé la lecture de l'état")
    etat = {}
    for inst in root.iter("Instance"):
        names = [e.text for e in inst.findall("ParaName")]
        vals = [e.text for e in inst.findall("ParaValue")]
        for n_, v_ in zip(names, vals):
            etat[n_] = v_
    return etat


def refresh_session_token(session, base, deadline=None):
    """Demande un jeton de session FRAIS au routeur.

    Le jeton obtenu avant le login expire (« page expirée ») : chaque
    écriture doit utiliser un jeton fraîchement demandé, comme le fait
    le navigateur (et le projet de référence avant son reboot).
    Retourne None si aucun jeton n'est obtenu.
    """
    r = session.get(base + "/?_type=loginData&_tag=login_entry",
                    timeout=_timeout(deadline, 15), verify=False)
    r.raise_for_status()
    info = r.json()
    return info.get("sess_token")


def ecrire_filtre(session, params, base, deadline=None):
    """Écrit la config globale. Retourne True si le routeur dit SUCC.

    Seul UrlFilterEnable change : les autres paramètres sont repris
    tels quels depuis la lecture d'état. La liste des URL n'est jamais
    touchée (aucun endpoint de liste n'est appelé).
    """
    sess_token = refresh_session_token(session, base, deadline)
    if not sess_token:
        return False
    body = (
        "IF_ACTION=Apply"
        "&MacFilterEnable=%s"
        "&UrlFilterTarget=%s"
        "&MacFilterTarget=%s"
        "&UrlFilterEnable=%s"
        "&_sessionTOKEN=%s" % (
            params["MacFilterEnable"], params["UrlFilterTarget"],
            params["MacFilterTarget"], params["UrlFilterEnable"],
            sess_token)
    )
    headers = {
        "Check": make_check_header(body),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    r = session.post(
        base + "/?_type=menuData&_tag=firewall_filterglobal_lua.lua&_="
        + str(int(time.time() * 1000)),
        data=body, headers=headers, timeout=_timeout(deadline, 20),
        verify=False)
    r.raise_for_status()
    try:
        root = ET.fromstring(r.content)
        err = root.findtext("IF_ERRORSTR") or ""
    except Exception:
        return False
    return err in ("SUCC", "SUCCESS", "OK")


def resume(etat):
    url_on = etat.get("UrlFilterEnable") == "1"
    mode = {"0": "Liste noire", "1": "Liste blanche"}.get(
        etat.get("UrlFilterTarget"), "?")
    mac = "activé" if etat.get("MacFilterEnable") == "1" else "désactivé"
    return ("Filtre d'URL : %s | Mode : %s | Filtre MAC : %s"
            % ("ACTIVÉ" if url_on else "DÉSACTIVÉ", mode, mac))


def status_label(url_filter_enable):
    """'1' -> 'blocked' (filtre actif, Roblox bloqué), '0' -> 'allowed'."""
    return "blocked" if url_filter_enable == "1" else "allowed"


# -------------------------------------------------------------- verrouillage
def lock_path():
    return os.path.join(tempfile.gettempdir(), LOCK_FILENAME)


class ExecutionLock:
    """Verrou non bloquant : une seule exécution à la fois."""

    def __init__(self, path):
        self.path = path
        self.fd = None

    def __enter__(self):
        if fcntl is None:
            raise ConfigError("verrou d'exécution non supporté sur "
                              "cette plateforme", error="LOCK_UNSUPPORTED")
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.fd)
            self.fd = None
            raise AlreadyRunning("une exécution est déjà en cours")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None
        return False


# ------------------------------------------------------------- joignabilité
def check_reachable(host, port=80, timeout=TCP_TIMEOUT):
    """Connexion TCP rapide : échoue vite hors du réseau domestique."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        raise RouterUnreachable("routeur %s:%s injoignable (%s)"
                                % (host, port, exc))


# ------------------------------------------------------------- configuration
def config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "config.json")


def load_config():
    """Fusionne config.json (prioritaire) et les constantes.

    Une valeur vide dans config.json ne remplace pas la constante.
    Lève ConfigError si aucun mot de passe n'est disponible.
    """
    cfg = {"router_ip": ROUTER_IP, "username": USERNAME,
           "password": PASSWORD}
    path = config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise ConfigError("fichier config.json illisible : %s" % exc,
                              error="INVALID_CONFIG")
        if not isinstance(data, dict):
            raise ConfigError("config.json doit contenir un objet JSON",
                              error="INVALID_CONFIG")
        for key in ("router_ip", "username", "password"):
            if data.get(key):
                cfg[key] = data[key]
    if not cfg["password"]:
        raise ConfigError(
            "mot de passe non configuré : renseignez config.json "
            "(copié depuis config.example.json) ou la constante PASSWORD",
            error="PASSWORD_NOT_CONFIGURED")
    return cfg


# ------------------------------------------------------------------- résultat
def make_result(success, status, previous_status, requested_action,
                verified, message, error=None, changed=None):
    result = {
        "success": success,
        "status": status,
        "previous_status": previous_status,
        "requested_action": requested_action,
        "verified": verified,
    }
    if changed is not None:
        result["changed"] = changed
    result["message"] = message
    if error is not None:
        result["error"] = error
    return result


def error_result(error, message, requested_action, previous_status=None):
    return make_result(False, "unknown", previous_status, requested_action,
                       False, message, error=error)


def format_text(result):
    """Rendu humain (option --format text). Jamais de JSON ici."""
    if result["success"]:
        etat = "ACTIVÉ (Roblox bloqué)" \
            if result["status"] == "blocked" else "DÉSACTIVÉ (Roblox autorisé)"
        ligne = "Filtre d'URL : %s" % etat
        if result.get("changed") is False:
            ligne += " — déjà dans cet état, aucune écriture"
        return "%s\nRésultat : succès, état vérifié." % ligne
    return "ERREUR [%s] : %s" % (result.get("error", "?"),
                                 result["message"])


# ------------------------------------------------------------------ arguments
USAGE = """Usage : toggle_filtre_url.py [on|off|toggle|status] [--format json|text]

  on       active le filtre d'URL (Roblox bloqué)
  off      désactive le filtre d'URL (Roblox autorisé)
  toggle   bascule (défaut si aucun argument)
  status   lecture seule de l'état réel, aucune écriture

Options :
  --format json   sortie JSON sur une ligne (défaut, contrat Tasker)
  --format text   sortie lisible par un humain
  --help          affiche cette aide

Codes de sortie : 0 succès, 2 déjà dans l'état demandé,
3 routeur injoignable, 4 authentification refusée,
5 écriture refusée, 6 état non confirmé, 7 exécution déjà en cours,
8 usage / configuration invalide.
"""


def parse_args(argv):
    action = None
    fmt = "json"
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--help", "-h"):
            return "help", fmt
        if arg == "--format":
            i += 1
            if i >= len(argv):
                raise UsageError("option --format sans valeur")
            fmt = argv[i]
        elif arg.startswith("--format="):
            fmt = arg.split("=", 1)[1]
        elif arg in ("on", "off", "toggle", "status") and action is None:
            action = arg
        else:
            raise UsageError("argument invalide : %s" % arg)
        i += 1
    if fmt not in ("json", "text"):
        raise UsageError("format invalide : %s (json ou text)" % fmt)
    if action is None:
        action = MODE
    return action, fmt


# ------------------------------------------------------------------ exécution
def execute(action):
    """Exécute une action. Retourne (code_de_sortie, dict_résultat).

    Ne lève jamais d'exception pour les erreurs connues : toute erreur
    devient un résultat structuré. Ne touche jamais au routeur si le
    verrou est déjà tenu ou si la configuration est invalide.
    """
    phase = "init"
    write_attempted = False
    session = None
    base = None
    try:
        with ExecutionLock(lock_path()):
            cfg = load_config()
            base = "http://" + cfg["router_ip"]
            deadline = Deadline(GLOBAL_TIMEOUT)
            phase = "precheck"
            check_reachable(cfg["router_ip"])
            session = new_session()
            try:
                phase = "login"
                zte_login(session, cfg["password"], base, cfg["username"],
                          deadline)
                phase = "read"
                etat = lire_etat_filtre(session, base, deadline)
                for key in ("UrlFilterEnable", "UrlFilterTarget",
                            "MacFilterEnable", "MacFilterTarget"):
                    if etat.get(key) is None:
                        raise StateReadError(
                            "paramètre %s absent de la réponse du routeur"
                            % key)
                if etat["UrlFilterEnable"] not in ("0", "1"):
                    raise StateReadError(
                        "valeur UrlFilterEnable inattendue : %r"
                        % etat["UrlFilterEnable"])
                if etat["UrlFilterTarget"] != "0":
                    raise ConfigError(
                        "mode liste blanche détecté : abandon sans "
                        "modification, pour préserver la liste noire",
                        error="WHITELIST_DETECTED")
                actuel = int(etat["UrlFilterEnable"])
                previous = status_label(etat["UrlFilterEnable"])

                if action == "status":
                    return EXIT_OK, make_result(
                        True, previous, None, "status", True,
                        "Filtre d'URL %s."
                        % ("activé — Roblox bloqué"
                           if actuel else "désactivé — Roblox autorisé"),
                        changed=False)

                cible = {"on": 1, "off": 0, "toggle": 1 - actuel}[action]
                if cible == actuel:
                    return EXIT_ALREADY, make_result(
                        True, previous, previous, action, True,
                        "Filtre d'URL déjà %s : aucune écriture."
                        % ("activé" if actuel else "désactivé"),
                        changed=False)

                # Une seule écriture : seul UrlFilterEnable change.
                nouveaux = dict(etat)
                nouveaux["UrlFilterEnable"] = str(cible)
                phase = "write"
                write_attempted = True
                try:
                    ok = ecrire_filtre(session, nouveaux, base, deadline)
                except requests.RequestException as exc:
                    raise StateNotConfirmed(
                        "réponse d'écriture perdue (%s) : état incertain, "
                        "vérifiez l'interface du routeur" % exc)
                if not ok:
                    raise WriteError("écriture refusée par le routeur")

                phase = "verify"
                try:
                    etat2 = lire_etat_filtre(session, base, deadline)
                except StateReadError as exc:
                    raise StateNotConfirmed(
                        "relecture impossible après écriture : %s" % exc)
                for key in ("UrlFilterEnable",) + PROTECTED_PARAMS:
                    if etat2.get(key) is None:
                        raise StateNotConfirmed(
                            "paramètre %s absent de la relecture" % key)
                for key in PROTECTED_PARAMS:
                    if etat2.get(key) != etat.get(key):
                        raise ProtectedChanged(
                            "paramètre protégé %s modifié (%s -> %s) : "
                            "l'opération est déclarée en échec"
                            % (key, etat.get(key), etat2.get(key)))
                if etat2["UrlFilterEnable"] != str(cible):
                    raise StateNotConfirmed(
                        "le routeur a répondu SUCC mais l'état n'a pas "
                        "changé (toujours %s)"
                        % etat2["UrlFilterEnable"])
                return EXIT_OK, make_result(
                    True, status_label(str(cible)), previous, action, True,
                    "Filtre d'URL %s — Roblox %s (état vérifié)."
                    % ("activé" if cible else "désactivé",
                       "bloqué" if cible else "autorisé"),
                    changed=True)
            finally:
                if session is not None:
                    zte_logout(session, base)
    except AlreadyRunning as exc:
        return EXIT_RUNNING, error_result(exc.error, str(exc), action)
    except ConfigError as exc:
        return EXIT_USAGE, error_result(exc.error, str(exc), action)
    except AuthError as exc:
        return EXIT_AUTH, error_result(exc.error, str(exc), action)
    except WriteError as exc:
        return EXIT_WRITE, error_result(exc.error, str(exc), action)
    except ProtectedChanged as exc:
        return EXIT_UNCONFIRMED, error_result(exc.error, str(exc), action)
    except StateNotConfirmed as exc:
        return EXIT_UNCONFIRMED, error_result(exc.error, str(exc), action)
    except StateReadError as exc:
        return EXIT_UNCONFIRMED, error_result(exc.error, str(exc), action)
    except RouterUnreachable as exc:
        return EXIT_UNREACHABLE, error_result(exc.error, str(exc), action)
    except RouterError as exc:
        return EXIT_UNREACHABLE, error_result(exc.error, str(exc), action)
    except OperationTimeout as exc:
        code = EXIT_UNCONFIRMED if write_attempted else EXIT_UNREACHABLE
        return code, error_result("TIMEOUT", str(exc), action)
    except requests.RequestException as exc:
        if phase in ("write", "verify"):
            return EXIT_UNCONFIRMED, error_result(
                "STATE_NOT_CONFIRMED",
                "erreur réseau pendant la vérification (%s) : état "
                "incertain, vérifiez l'interface du routeur" % exc, action)
        if isinstance(exc, requests.HTTPError):
            return EXIT_UNREACHABLE, error_result(
                "ROUTER_ERROR", "erreur HTTP du routeur : %s" % exc, action)
        return EXIT_UNREACHABLE, error_result(
            "ROUTER_UNREACHABLE", "routeur injoignable : %s" % exc, action)
    except Exception as exc:  # jamais de traceback brut vers Tasker
        return EXIT_UNCONFIRMED, error_result(
            "INTERNAL_ERROR", "erreur inattendue : %s" % exc, action)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if requests is None:
        result = error_result(
            "MISSING_DEPENDENCY",
            "le module 'requests' est introuvable : pip install requests",
            "unknown")
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_USAGE
    try:
        action, fmt = parse_args(argv)
    except UsageError as exc:
        result = error_result(exc.error, str(exc), "unknown")
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_USAGE
    if action == "help":
        print(USAGE, end="")
        return EXIT_OK
    code, result = execute(action)
    if fmt == "text":
        print(format_text(result))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
