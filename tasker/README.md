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

| Code | Sens | `error` associé |
| ---: | ---- | --------------- |
| 0 | succès (changé + vérifié) | — |
| 2 | déjà dans l'état demandé, aucune écriture | — |
| 3 | routeur injoignable | `ROUTER_UNREACHABLE`, `TIMEOUT` (avant écriture) |
| 4 | authentification refusée | `AUTH_FAILED` |
| 5 | écriture refusée / échouée | `WRITE_FAILED` |
| 6 | état final non confirmé | `STATE_READ_FAILED`, `STATE_NOT_CONFIRMED`, `PROTECTED_PARAMS_CHANGED`, `TIMEOUT` (après écriture), `INTERNAL_ERROR` |
| 7 | exécution déjà en cours | `ALREADY_RUNNING` |
| 8 | usage / configuration invalide | `INVALID_USAGE`, `INVALID_CONFIG`, `PASSWORD_NOT_CONFIGURED`, `CONFIG_PERMISSIONS`, `WHITELIST_DETECTED`, `MISSING_DEPENDENCY`, `LOCK_UNSUPPORTED` |
| 9 | routeur joignable mais réponse invalide | `ROUTER_ERROR` |

> **Code 2 = succès, pas une erreur** : le code 2 signifie « déjà
> dans l'état demandé, aucune écriture ». La tâche Tasker doit le
> traiter comme un succès (branche 0/2 = succès), pas comme un
> échec. Un appui sur « Bloquer » alors que Roblox est déjà bloqué
> est un succès, sans écriture.
>
> **Changement de contrat (v2.0.0)** : `ROUTER_ERROR` sortait
> auparavant en code 3 ; il sort désormais en code 9.

Ajouter un widget Tasker sur l'écran d'accueil, lié à cette tâche.
Des profils horaires Tasker peuvent appeler la même tâche avec `on`
ou `off` pour automatiser les plages d'accès.

## Anti-double-appui : deux widgets explicites

Plutôt qu'un seul widget qui bascule (`toggle`), le pattern
recommandé est **deux widgets explicites** : « Bloquer » appelle la
tâche avec `on`, « Autoriser » avec `off`. Les deux actions sont
idempotentes grâce au no-op (code 2) : un double appui sur le même
widget ne remet pas l'état initial, il confirme simplement l'état
déjà demandé. Un double appui sur un widget `toggle`, lui, annulerait
la première bascule.

## Retour d'état sur le bouton

Le wrapper ne change pas l'icône du widget tout seul. Pour afficher
l'état réel sur le bouton, exécuter la commande `status` (lecture
seule, aucune écriture) à l'ouverture du widget — ou sur une tuile
Quick Settings Tasker — puis afficher l'icône ou le libellé selon
le champ `status` du JSON (`blocked` / `allowed`).

## Alternative sans Tasker : Termux:Widget

Sans Tasker, Termux:Widget permet de créer un raccourci sur l'écran
d'accueil qui lance directement un script dans `~/.shortcuts/`.

## Prérequis : autoriser les applications externes

Pour que le plugin Termux:Tasker fonctionne, Termux doit autoriser
les applications externes : dans `~/.termux/termux.properties`,
ajouter `allow-external-apps=true`, puis appliquer avec
`termux-reload-settings`. Sans cela, le plugin ne démarre pas.

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
- `config.json` doit avoir des droits `600` ou plus stricts, sinon
  le script refuse de démarrer (`CONFIG_PERMISSIONS`, code 8) :
  `chmod 600 ~/config.json`. Sous Termux, ne pas placer ce fichier
  dans `~/storage` (le stockage partagé ne supporte pas `chmod`).

## Exporter le projet Tasker (.prj.xml) pour contribuer

Pour proposer la tâche Tasker au dépôt (elle n'y est pas encore,
l'export ne peut pas être fait depuis ici) : appui long sur le
projet dans Tasker → Export → le fichier `.prj.xml` généré peut
ensuite être proposé. **Vérifier avant tout envoi qu'il ne contient
aucun secret** (mot de passe, chemins personnels) : un export
Tasker peut embarquer des variables du projet.

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
