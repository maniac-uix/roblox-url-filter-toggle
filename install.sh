#!/bin/sh
# Installation de Roblox URL Filter Toggle dans Termux.
# Usage : sh install.sh
# Idempotent : relancer ce script ne touche jamais à un config.json
# existant et ne demande ni ne stocke jamais le mot de passe admin.
# Ce script ne crée PAS config.json : il dépose config.example.json
# et affiche les étapes pour le créer (copie + chmod 600).
set -e
umask 077

# Référence Git à télécharger : SHA complet (40 caractères) du commit
# dont le contenu doit être installé. Règle d'épinglage : REF doit
# désigner le commit dont les fichiers installés seront taggés ; à
# chaque modification d'un fichier installé (script, config.example.json,
# requirements.txt, tasker/*), remettre REF sur le nouveau commit avant
# de tagger, puis vérifier que git diff <REF> <tag> --
# toggle_filtre_url.py config.example.json requirements.txt tasker/
# est vide. Pour suivre main, passer REF=main en variable
# d'environnement (déconseillé : contenu non figé).
REF="${REF:-a1a4e9c249bcbba97471e32585e1917b745f68fc}"
REPO="maniac-uix/roblox-url-filter-toggle"
BASE="https://raw.githubusercontent.com/$REPO/$REF"

# 1. Vérifier l'environnement Termux.
if ! command -v pkg >/dev/null 2>&1; then
    echo "Erreur : ce script doit être lancé dans Termux (pkg introuvable)." >&2
    exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
    echo "Erreur : curl est requis (pkg install -y curl)." >&2
    exit 1
fi

# 2. Python + dépendances.
pkg update -y
pkg install -y python
mkdir -p ~/.termux/tasker
cd ~
curl -fsSL "$BASE/requirements.txt" -o requirements.txt
pip install -r requirements.txt

# 3. Télécharger le script et le wrapper (mise à jour si relancé).
curl -fsSL "$BASE/toggle_filtre_url.py" -o toggle_filtre_url.py
curl -fsSL "$BASE/tasker/roblox_toggle" -o .termux/tasker/roblox_toggle
chmod +x toggle_filtre_url.py .termux/tasker/roblox_toggle

# 4. Exemple de configuration, sans jamais écraser config.json.
if [ -f config.json ]; then
    echo "config.json existant conservé : rien n'a été écrasé."
else
    if [ ! -f config.example.json ]; then
        curl -fsSL "$BASE/config.example.json" -o config.example.json
    fi
    echo "config.json absent : il n'a PAS été créé automatiquement."
fi

echo ""
echo "Étapes suivantes :"
echo "  1. Si config.json n'existe pas encore :"
echo "       cp config.example.json config.json"
echo "       nano config.json   # renseigner le mot de passe admin"
echo "       chmod 600 config.json"
echo "  2. Autoriser les applications externes dans Termux (requis pour"
echo "     le plugin Termux:Tasker) — ce script ne modifie PAS"
echo "     termux.properties tout seul, à vous de le faire :"
echo "       echo 'allow-external-apps=true' >> ~/.termux/termux.properties"
echo "       termux-reload-settings"
echo "  3. Créer la tâche Tasker (voir tasker/README.md du dépôt), puis"
echo "     tester sur le WiFi maison : python toggle_filtre_url.py status"
