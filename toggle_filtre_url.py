#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BASCULE ON/OFF du "Filtre d'URL" — ZTE F6600P (Orange Maroc Livebox WiFi 6).

Ce que fait ce script :
  - se connecte au routeur (flux validé par les sondes),
  - lit l'état actuel du filtre d'URL (Activé/Désactivé) et du mode (Liste noire),
  - VALIDE le format d'écriture en réécrivant les valeurs actuelles (sans rien changer),
  - bascule le Filtre d'URL vers l'état demandé,
  - RELIT l'état pour confirmer que la bascule a bien eu lieu.

Ce qu'il NE fait PAS :
  - il ne touche JAMAIS à la liste des URL (tes règles Roblox restent intactes),
  - il ne touche ni au filtre MAC, ni au mode (reste en Liste noire),
  - il n'affiche JAMAIS "succès" sans avoir vérifié le nouvel état.

Utilisation dans Pydroid 3 :
  - colle ton mot de passe dans PASSWORD = "" ci-dessous (reste sur ton téléphone),
  - exécute le script : par défaut il BASCULE (toggle),
  - pour forcer : ajoute un argument -> on | off | toggle
    (dans Pydroid 3 : menu "..." pendant l'exécution, ou modifie MODE ci-dessous).
"""

import base64
import getpass
import hashlib
import random
import re
import sys
import time
import warnings
import xml.etree.ElementTree as ET

warnings.filterwarnings("ignore")

try:
    import requests
except ImportError:
    print("ERREUR : le module 'requests' est introuvable.")
    print("Dans Pydroid 3 : menu Pip -> installer 'requests', puis relancez.")
    sys.exit(1)

# ---------------------------------------------------------------- paramètres
ROUTER_IP = "192.168.11.1"
USERNAME = "user"
BASE = "http://" + ROUTER_IP
# Colle le mot de passe admin entre les guillemets (reste sur TON téléphone).
# Laisse vide ("") pour qu'il soit demandé à chaque exécution.
PASSWORD = ""
# Mode par défaut si aucun argument : "toggle" (bascule), "on" ou "off".
MODE = "toggle"

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


def zte_login(session, password):
    """Connexion validée par les sondes n°1 à n°5. Retourne sess_token ou None."""
    r = session.get(BASE + "/?_type=loginData&_tag=login_entry",
                    timeout=15, verify=False)
    r.raise_for_status()
    info = r.json()
    if info.get("lockingTime", 0) not in (0, None):
        print("ERREUR : routeur verrouillé %s s : %s"
              % (info.get("lockingTime"), info.get("loginErrMsg")))
        return None
    sess_token = info.get("sess_token")
    if not sess_token:
        print("ERREUR : pas de sess_token :", str(info)[:200])
        return None

    rnd = "".join(random.choice("0123456789ABCDEF") for _ in range(16))
    r = session.get(BASE + "/?_type=loginData&_tag=login_token&_=" + rnd,
                    timeout=15, verify=False)
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
        print("ERREUR : login_token introuvable :", r.text[:200])
        return None

    pwd_hash = hashlib.sha256(
        (password + login_token).encode("utf-8")).hexdigest()
    r = session.post(
        BASE + "/?_type=loginData&_tag=login_entry",
        data={"action": "login", "Password": pwd_hash,
              "Username": USERNAME, "_sessionTOKEN": sess_token},
        timeout=15, verify=False,
    )
    r.raise_for_status()
    try:
        res = r.json()
    except Exception:
        print("ERREUR : réponse de connexion inattendue :", r.text[:500])
        return None
    if res.get("loginErrMsg"):
        print("ERREUR de connexion :", res.get("loginErrMsg"))
        return None
    if res.get("lockingTime", 0) not in (0, None):
        print("ERREUR : routeur verrouillé (%s s)." % res.get("lockingTime"))
        return None
    print("CONNECTÉ au routeur.")
    return sess_token


def zte_logout(session):
    try:
        session.get(BASE + "/?_type=loginData&_tag=logout", timeout=10,
                    verify=False)
    except Exception:
        pass


# ------------------------------------------------------------ filtre d'URL
def lire_etat_filtre(session):
    """Lit OBJ_FWBASE_ID. Retourne dict ou None."""
    # Le routeur exige que la page (menuView) soit chargée avant de servir
    # ses données (menuData) : sans ça, il répond SessionTimeout.
    # (Séquence identique à la sonde n°5, qui fonctionnait.)
    session.get(
        BASE + "/?_type=menuView&_tag=filterCriteria&Menu3Location=0",
        timeout=25, verify=False)
    r = session.get(
        BASE + "/?_type=menuData&_tag=firewall_filterglobal_lua.lua",
        timeout=20, verify=False)
    r.raise_for_status()
    try:
        root = ET.fromstring(r.content)
    except Exception:
        print("Réponse inattendue :", r.text[:300])
        return None
    if (root.findtext("IF_ERRORSTR") or "") not in ("SUCC", "SUCCESS", "OK"):
        print("Erreur routeur :", r.text[:300])
        return None
    etat = {}
    for inst in root.iter("Instance"):
        names = [e.text for e in inst.findall("ParaName")]
        vals = [e.text for e in inst.findall("ParaValue")]
        for n_, v_ in zip(names, vals):
            etat[n_] = v_
    return etat


def refresh_session_token(session):
    """Demande un jeton de session FRAIS au routeur.

    Le jeton obtenu avant le login expire (« page expirée ») : chaque
    écriture doit utiliser un jeton fraîchement demandé, comme le fait
    le navigateur (et le projet de référence avant son reboot).
    """
    r = session.get(BASE + "/?_type=loginData&_tag=login_entry",
                    timeout=15, verify=False)
    r.raise_for_status()
    info = r.json()
    token = info.get("sess_token")
    if not token:
        print("ERREUR : pas de sess_token frais :", str(info)[:200])
    return token


def ecrire_filtre(session, params):
    """Écrit la config globale. Retourne True si le routeur dit SUCC."""
    sess_token = refresh_session_token(session)
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
        BASE + "/?_type=menuData&_tag=firewall_filterglobal_lua.lua&_="
        + str(int(time.time() * 1000)),
        data=body, headers=headers, timeout=20, verify=False)
    r.raise_for_status()
    try:
        root = ET.fromstring(r.content)
        err = root.findtext("IF_ERRORSTR") or ""
    except Exception:
        print("Réponse d'écriture inattendue :", r.text[:500])
        return False
    if err not in ("SUCC", "SUCCESS", "OK"):
        print("Le routeur a refusé l'écriture (IF_ERRORSTR=%s)." % err)
        print("Réponse complète :", r.text[:800])
        return False
    return True


def resume(etat):
    url_on = etat.get("UrlFilterEnable") == "1"
    mode = {"0": "Liste noire", "1": "Liste blanche"}.get(
        etat.get("UrlFilterTarget"), "?")
    mac = "activé" if etat.get("MacFilterEnable") == "1" else "désactivé"
    return ("Filtre d'URL : %s | Mode : %s | Filtre MAC : %s"
            % ("ACTIVÉ" if url_on else "DÉSACTIVÉ", mode, mac))


# ---------------------------------------------------------------------- main
def main():
    print("=" * 64)
    print("BASCULE du Filtre d'URL — ZTE F6600P")
    print("=" * 64)
    mode = (sys.argv[1] if len(sys.argv) > 1 else MODE).lower()
    if mode not in ("on", "off", "toggle"):
        print("Mode '%s' invalide : utilisez on, off ou toggle." % mode)
        return
    password = PASSWORD or getpass.getpass("Mot de passe admin du routeur : ")
    if not password:
        print("Mot de passe vide, abandon.")
        return

    session = new_session()
    sess_token = zte_login(session, password)
    if not sess_token:
        print("CONNEXION ÉCHOUÉE.")
        return

    etat = lire_etat_filtre(session)
    if not etat:
        print("Lecture de l'état impossible.")
        zte_logout(session)
        return
    print("État actuel  -> " + resume(etat))

    actuel = int(etat.get("UrlFilterEnable", "0"))
    cible = {"on": 1, "off": 0, "toggle": 1 - actuel}[mode]

    # Étape 1 : validation du format d'écriture (réécrit les valeurs actuelles,
    # ne change RIEN).
    print("\n[1/3] Validation du format d'écriture (sans changement)...")
    if not ecrire_filtre(session, etat):
        print("VALIDATION ÉCHOUÉE : aucune modification effectuée.")
        print("Copiez tout ce texte et envoyez-le à Kibou.")
        zte_logout(session)
        return
    print("Format d'écriture validé par le routeur.")

    if cible == actuel:
        print("\nDéjà dans l'état demandé (%s) : rien à faire."
              % ("ACTIVÉ" if cible else "DÉSACTIVÉ"))
        zte_logout(session)
        return

    # Étape 2 : bascule réelle (seul UrlFilterEnable change).
    print("\n[2/3] Bascule du Filtre d'URL vers : %s..."
          % ("ACTIVÉ" if cible else "DÉSACTIVÉ"))
    nouveaux = dict(etat)
    nouveaux["UrlFilterEnable"] = str(cible)
    if not ecrire_filtre(session, nouveaux):
        print("ÉCHEC de la bascule : l'état n'a pas été modifié.")
        print("Copiez tout ce texte et envoyez-le à Kibou.")
        zte_logout(session)
        return

    # Étape 3 : vérification par relecture.
    print("\n[3/3] Vérification du nouvel état...")
    etat2 = lire_etat_filtre(session)
    zte_logout(session)
    print("Déconnecté proprement du routeur.")
    if not etat2:
        print("Relecture impossible : état incertain, vérifiez dans "
              "l'interface web (Critères de filtrage).")
        return
    print("Nouvel état  -> " + resume(etat2))
    if int(etat2.get("UrlFilterEnable", "-1")) == cible:
        print("\n*** SUCCÈS : le Filtre d'URL est maintenant %s. ***"
              % ("ACTIVÉ" if cible else "DÉSACTIVÉ"))
        print("La liste des URL (Roblox) n'a pas été modifiée.")
    else:
        print("\n*** ÉCHEC : l'état n'a pas changé malgré la réponse SUCC. ***")
        print("Copiez tout ce texte et envoyez-le à Kibou.")
    print("=" * 64)


if __name__ == "__main__":
    main()
