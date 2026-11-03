# Bascule du filtre d'URL Roblox — ZTE F6600P

Bascule ON/OFF du **filtre d'URL** du routeur **ZTE F6600P** (Orange Maroc
Livebox WiFi 6) pour autoriser ou bloquer l'accès à Roblox, sans jamais
toucher à la liste des URL filtrées.

Version 2 : fiabilisée (phases 1, 2 et 3 de l'audit du 2026-11-04) —
codes de sortie distincts, verrou d'exécution, vérification des
paramètres protégés, sortie JSON pour Tasker, tests et CI.

## Principe

Le script `toggle_filtre_url.py` :

1. vérifie que le routeur est joignable en local (connexion TCP rapide),
2. se connecte à l'interface web du routeur (réseau local uniquement),
3. lit l'état actuel du filtre d'URL (`Activé`/`Désactivé`) et son mode
   (`Liste noire`),
4. si l'état demandé est déjà l'état actuel : **aucune écriture**,
5. sinon, bascule le filtre en **une seule écriture**,
6. **relit l'état pour confirmer** que la bascule a bien eu lieu et que
   les paramètres protégés (mode, filtre MAC) sont inchangés.

Ce qu'il ne fait **jamais** :

- il ne touche pas à la liste des URL (les règles Roblox restent intactes),
- il ne touche ni au filtre MAC, ni au mode (reste en `Liste noire`) —
  si le mode liste blanche est détecté au départ, il abandonne sans
  rien modifier,
- il n'écrit rien si l'un des quatre paramètres lus
  (`UrlFilterEnable`, `UrlFilterTarget`, `MacFilterEnable`,
  `MacFilterTarget`) ne vaut pas strictement `0` ou `1` (valeur
  absente, vide ou inattendue → abandon sans écriture),
- il n'affiche jamais « succès » sans avoir vérifié le nouvel état,
- il ne bascule jamais à l'aveugle (réponse perdue = échec déclaré).

Détails techniques : l'écriture passe par l'API web du routeur avec un
jeton de session frais à chaque écriture et un en-tête `Check` signé
RSA-4096 (clé publique du F6600P, publique et non secrète). Le
protocole est identique à celui de la v1, validé avec ce routeur.

## Prérequis

- Un routeur ZTE F6600P (Orange Maroc Livebox WiFi 6), accessible en local
  sur `192.168.11.1` (modifiable dans `config.json`).
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

### 2. Copier les fichiers

Télécharger `toggle_filtre_url.py`, puis dans Termux :

```sh
cp ~/storage/downloads/toggle_filtre_url.py ~/
```

### 3. Configurer (une fois, reste sur le téléphone)

Copier l'exemple vers `config.json` à côté du script, puis renseigner
le mot de passe admin :

```sh
cp config.example.json config.json
nano config.json
chmod 600 config.json
```

```json
{
  "router_ip": "192.168.11.1",
  "username": "user",
  "password": "ton_mot_de_passe_admin"
}
```

> `config.json` est dans `.gitignore` : il ne doit **jamais** être
> commité. La version publiée de ce dépôt ne contient aucun mot de
> passe (`config.example.json` a un mot de passe vide).
>
> Compatibilité v1 : si `config.json` est absent, le script utilise
> la constante `PASSWORD` du script (vide par défaut). Si aucun mot
> de passe n'est disponible : erreur `PASSWORD_NOT_CONFIGURED`
> (code 8). Il n'y a plus de saisie interactive (`getpass` supprimé) :
> l'exécution Tasker est totalement non interactive.

### 4. Tester (sur le WiFi maison)

```sh
cd ~ && python toggle_filtre_url.py status
cd ~ && python toggle_filtre_url.py toggle
```

La sortie est du JSON ; pour un affichage lisible, ajoutez
`--format text`.

## Utilisation

```sh
python toggle_filtre_url.py           # bascule (toggle, par défaut)
python toggle_filtre_url.py on        # active le filtre (Roblox bloqué)
python toggle_filtre_url.py off       # désactive le filtre (Roblox autorisé)
python toggle_filtre_url.py toggle    # bascule
python toggle_filtre_url.py status    # lecture seule, aucune écriture
python toggle_filtre_url.py toggle --format text   # sortie lisible
```

## Contrat JSON (sortie par défaut)

Une seule ligne JSON, cohérente avec le code de sortie. Exemple de
succès :

```json
{"success": true, "status": "blocked", "previous_status": "allowed", "requested_action": "toggle", "verified": true, "changed": true, "message": "Filtre d'URL activé — Roblox bloqué (état vérifié)."}
```

Exemple d'échec :

```json
{"success": false, "status": "unknown", "previous_status": null, "requested_action": "toggle", "verified": false, "message": "routeur 192.168.11.1:80 injoignable (…)", "error": "ROUTER_UNREACHABLE"}
```

Champs :

| Champ | Sens |
| ----- | ---- |
| `success` | `true` si l'opération est confirmée |
| `status` | état final : `blocked` (filtre actif), `allowed` (filtre inactif), `unknown` (échec) |
| `previous_status` | état avant l'opération (`null` si inconnu) |
| `requested_action` | `on`, `off`, `toggle` ou `status` |
| `verified` | `true` si l'état a été relu et confirmé sur le routeur |
| `changed` | présent sur les succès : `true` si une écriture a eu lieu, `false` si déjà dans l'état demandé |
| `message` | message lisible (français) |
| `error` | code machine de l'erreur, présent uniquement en cas d'échec |

## Codes de sortie

| Code | Sens | `error` associé |
| ---: | ---- | --------------- |
| 0 | succès (changé + vérifié) | — |
| 2 | déjà dans l'état demandé, aucune écriture | — |
| 3 | routeur injoignable | `ROUTER_UNREACHABLE`, `ROUTER_ERROR`, `TIMEOUT` (avant écriture) |
| 4 | authentification refusée | `AUTH_FAILED` |
| 5 | écriture refusée / échouée | `WRITE_FAILED` |
| 6 | état final non confirmé | `STATE_READ_FAILED`, `STATE_NOT_CONFIRMED`, `PROTECTED_PARAMS_CHANGED`, `TIMEOUT` (après écriture), `INTERNAL_ERROR` |
| 7 | exécution déjà en cours | `ALREADY_RUNNING` |
| 8 | usage / configuration invalide | `INVALID_USAGE`, `INVALID_CONFIG`, `PASSWORD_NOT_CONFIGURED`, `WHITELIST_DETECTED`, `MISSING_DEPENDENCY`, `LOCK_UNSUPPORTED` |

## Bouton Tasker

Voir [`tasker/README.md`](tasker/README.md) : wrapper Termux:Tasker,
lecture de `roblox_result.json` et `roblox_exit.txt`, branchement sur
`success` / `status` / code de sortie, et note de migration depuis
la v1.

## Tests et CI

Les tests (`tests/`, `unittest` + `unittest.mock`) simulent le routeur
et ne nécessitent aucun routeur physique. Ils couvrent
l'authentification, la lecture d'état, la bascule (no-op sans
écriture, une seule écriture), les paramètres protégés et le contrat
Tasker (formes JSON, codes de sortie), ainsi que la cryptographie
(structure PKCS#1 v1.5, en-tête `Check`, longueurs de ciphertext) et
la validation stricte des paramètres avant écriture.

```sh
python3 -m unittest discover -s tests -v
```

La CI (`.github/workflows/tests.yml`) lance ces tests sur Python 3.11
et 3.12 à chaque push et pull request.

## Vérification

Après une bascule, vérifier dans l'interface du routeur (Critères de
filtrage) que le filtre d'URL a bien basculé, sans modification des
URL ni du mode Liste noire. En cas de problème, voir
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

## Sécurité

- Le mot de passe admin reste sur l'appareil qui exécute le script
  (`config.json`, permissions `600`, jamais commité).
- Ne jamais exposer l'administration du routeur sur Internet.
- Le script parle au routeur en HTTP, comme son interface web : c'est
  le protocole réellement supporté par le F6600P, utilisable
  uniquement sur le réseau local.
- Désactiver l'optimisation batterie pour Termux et Termux:Tasker
  (sinon Android peut tuer l'exécution).

## Migration v1 → v2

- Sortie JSON au lieu de texte libre : la tâche Tasker doit être mise
  à jour (voir `tasker/README.md`).
- Configuration par `config.json` au lieu de `getpass` : créer le
  fichier avant la première exécution.
- Le protocole routeur et le comportement du bouton sont inchangés :
  une seule bascule, état vérifié, liste noire et filtre MAC intacts.
- Voir [`CHANGELOG.md`](CHANGELOG.md) pour la liste complète des
  changements.

## Licence

MIT — voir `LICENSE`.
