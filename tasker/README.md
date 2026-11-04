# Intégration Tasker (v2)

Ce dossier contient l'exécutable Termux:Tasker et son mode d'emploi.
Le script Python lui-même reste à la racine du dépôt.

## Installation

### 1. Côté Termux (une fois)

```sh
mkdir -p ~/.termux/tasker
cp tasker/roblox_toggle ~/.termux/tasker/roblox_toggle
chmod +x ~/.termux/tasker/roblox_toggle
```

Copier aussi `toggle_filtre_url.py` et `config.json` (voir README principal)
dans `~` :

```sh
cp toggle_filtre_url.py ~/
cp config.json ~/          # ne jamais committer ce fichier
chmod 600 ~/config.json
```

### 2. Côté Tasker

Nouvelle tâche, par exemple « Roblox Toggle », avec ces actions :

1. **Plugin → Termux:Tasker** → configuration → Executable : `roblox_toggle`
   (si un champ Arguments existe : y mettre `%par1` pour
   `on` / `off` / `toggle` / `status`).
2. **Fichier → Lire un fichier** : `Download/roblox_result.json`
   → vers `%ROBLOX_JSON`.
3. **Fichier → Lire un fichier** : `Download/roblox_exit.txt`
   → vers `%ROBLOX_EXIT`.
4. Analyser `%ROBLOX_JSON` (action **JSON Read** ou JavaScriptlet
   `JSON.parse`) et brancher selon les champs :
   - `success` = true, `status` = `blocked` → Roblox bloqué.
   - `success` = true, `status` = `allowed` → Roblox autorisé.
   - `success` = false → afficher `message` et, si besoin, `error`
     (voir la table des codes dans le README principal).
5. **Alerte → Flash** (ou notification) avec le résultat.

Le code de sortie `%ROBLOX_EXIT` distingue en plus les cas que le JSON
résume ainsi :

| Code | Sens |
| ---: | ---- |
| 0 | succès (changé + vérifié) |
| 2 | déjà dans l'état demandé, aucune écriture |
| 3 | routeur injoignable |
| 4 | authentification refusée |
| 5 | écriture refusée |
| 6 | état final non confirmé |
| 7 | exécution déjà en cours |
| 8 | usage / configuration invalide |

Ajouter un widget Tasker sur l'écran d'accueil, lié à cette tâche.
Des profils horaires Tasker peuvent appeler la même tâche avec `on`
ou `off` pour automatiser les plages d'accès.

## Notes

- Le verrou d'exécution du script refuse un second lancement tant que
  le premier n'est pas terminé (code 7) : deux clics rapides ne
  provoquent plus de double bascule.
- La sortie d'erreur éventuelle du script est isolée dans
  `Download/roblox_result.err` : elle ne pollue jamais le JSON.
- Les résultats passent par des fichiers temporaires puis un
  renommage atomique : Tasker ne lit jamais un fichier incomplet si
  l'exécution est interrompue pendant l'écriture. Chaque exécution
  utilise ses propres fichiers temporaires (`mktemp`), donc deux
  déclenchements rapprochés ne peuvent pas se marcher dessus.
- Désactiver l'optimisation batterie pour Termux et Termux:Tasker
  (sinon Android peut tuer l'exécution).

## Migration depuis la v1

- La v1 écrivait un texte libre dans `roblox_result.txt` ; la v2 écrit
  du JSON dans `roblox_result.json` et le code de sortie dans
  `roblox_exit.txt`. La tâche Tasker doit être mise à jour en
  conséquence : l'ancienne tâche qui affichait le texte brut ne
  comprendra pas le JSON.
- La v1 demandait le mot de passe via `getpass` si `PASSWORD` était
  vide ; la v2 ne le fait plus : créer `config.json` (voir README
  principal) avant la première exécution, sinon erreur
  `PASSWORD_NOT_CONFIGURED` (code 8).
- Ne pas mélanger les deux versions : remplacer le script, le wrapper
  et la tâche Tasker en une fois.
