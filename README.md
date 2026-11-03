# Bascule du filtre d'URL Roblox — ZTE F6600P

Bascule ON/OFF du **filtre d'URL** du routeur **ZTE F6600P** (Orange Maroc
Livebox WiFi 6) pour autoriser ou bloquer l'accès à Roblox, sans jamais
toucher à la liste des URL filtrées.

## Principe

Le script `toggle_filtre_url.py` :

1. se connecte à l'interface web du routeur (réseau local uniquement),
2. lit l'état actuel du filtre d'URL (`Activé`/`Désactivé`) et son mode
   (`Liste noire`),
3. **valide le format d'écriture** en réécrivant les valeurs actuelles
   (sans rien changer),
4. bascule le filtre vers l'état demandé,
5. **relit l'état pour confirmer** que la bascule a bien eu lieu.

Ce qu'il ne fait **jamais** :

- il ne touche pas à la liste des URL (les règles Roblox restent intactes),
- il ne touche ni au filtre MAC, ni au mode (reste en `Liste noire`),
- il n'affiche jamais « succès » sans avoir vérifié le nouvel état.

Détails techniques : l'écriture passe par l'API web du routeur avec un
jeton de session frais à chaque écriture et un en-tête `Check` signé RSA-4096
(clé publique du F6600P, publique et non secrète).

## Prérequis

- Un routeur ZTE F6600P (Orange Maroc Livebox WiFi 6), accessible en local
  sur `192.168.11.1`.
- Un téléphone Android sur le WiFi de la maison, avec :
  - **Termux** (via F-Droid, pas la version Play Store, abandonnée),
  - **Termux:Tasker** (le plugin),
  - **Tasker** (optionnel, pour le widget et la planification).
- Python et le module `requests` dans Termux.

## Installation

### 1. Préparer Termux (une fois)

```sh
pkg update -y && pkg install -y python
pip install requests
termux-setup-storage
```

(Accepter la demande d'accès aux fichiers quand elle apparaît.)

### 2. Copier le script

Télécharger `toggle_filtre_url.py`, puis dans Termux :

```sh
cp ~/storage/downloads/toggle_filtre_url.py ~/
```

### 3. Mettre le mot de passe (une fois, reste sur le téléphone)

```sh
nano ~/toggle_filtre_url.py
```

Renseigner la ligne :

```python
PASSWORD = "ton_mot_de_passe_admin"
```

`Ctrl+O`, Entrée, `Ctrl+X` pour sauvegarder et quitter.

> Le mot de passe reste dans ce fichier, **sur le téléphone uniquement**.
> La version publiée ici a `PASSWORD = ""` : elle demande le mot de passe
> à chaque exécution si la ligne n'est pas renseignée.

### 4. Tester (sur le WiFi maison)

```sh
cd ~ && python toggle_filtre_url.py toggle
```

Le script affiche la bascule puis la relecture de confirmation.

## Utilisation

```sh
python toggle_filtre_url.py           # bascule (toggle, par défaut)
python toggle_filtre_url.py on        # active le filtre (Roblox bloqué)
python toggle_filtre_url.py off       # désactive le filtre (Roblox autorisé)
```

## Bouton Tasker (optionnel)

### 1. Exécutable pour le plugin Termux:Tasker

```sh
mkdir -p ~/.termux/tasker
nano ~/.termux/tasker/roblox_toggle
```

Contenu :

```sh
#!/data/data/com.termux/files/usr/bin/sh
# $1 = on / off / toggle (défaut : toggle)
python ~/toggle_filtre_url.py "${1:-toggle}" > ~/storage/downloads/roblox_result.txt 2>&1
```

```sh
chmod +x ~/.termux/tasker/roblox_toggle
```

### 2. Tâche Tasker

Nouvelle tâche, 3 actions :

1. **Plugin → Termux:Tasker** → configuration → Executable : `roblox_toggle`
   (si un champ Arguments existe : y mettre `%par1` pour on/off/toggle).
2. **Fichier → Lire un fichier** : `Download/roblox_result.txt` → vers
   `%ROBLOX_RESULT`.
3. **Alerte → Flash** : texte `%ROBLOX_RESULT`.

Ajouter un widget Tasker sur l'écran d'accueil, lié à cette tâche. Le Flash
affiche le résumé (état avant/après + confirmation de relecture).

Des profils horaires Tasker peuvent ensuite appeler la même tâche avec `on`
ou `off` pour automatiser les plages d'accès (par exemple : autorisé le
soir en semaine, bloqué en dehors).

## Vérification

Après une bascule, vérifier dans l'interface du routeur (Critères de
filtrage) que le filtre d'URL a bien basculé, sans modification des URL
ni du mode Liste noire.

## Sécurité

- Le mot de passe admin reste sur l'appareil qui exécute le script.
- Ne jamais exposer l'administration du routeur sur Internet.
- Désactiver l'optimisation batterie pour Termux et Termux:Tasker
  (sinon Android peut tuer l'exécution).

## Licence

MIT — voir `LICENSE`.
