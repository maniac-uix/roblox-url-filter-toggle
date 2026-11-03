# Journal des modifications

## v1.0.0 — Fiabilisation (phases 1, 2 et 3 de l'audit du 2026-11-04)

Par rapport à la première version publiée (script seul + README) :

### Fiabilité (phase 1)

- **Suppression de la validation par réécriture** : le script lisait l'état,
  réécrivait les valeurs actuelles, puis écrivait la bascule. Il ne fait
  plus qu'**une seule écriture**, uniquement si l'état demandé diffère de
  l'état actuel. Si l'état demandé est déjà l'état actuel : **aucune
  écriture** (code de sortie 2).
- **Codes de sortie distincts** (voir README) : succès, déjà dans l'état,
  routeur injoignable, authentification refusée, écriture refusée, état
  non confirmé, exécution déjà en cours, usage/configuration invalide.
- **Verrou d'exécution** (`fcntl.flock` non bloquant) : un second
  lancement pendant une exécution en cours échoue proprement (code 7)
  sans toucher au routeur.
- **Vérification des paramètres protégés** : `UrlFilterTarget`,
  `MacFilterEnable` et `MacFilterTarget` sont comparés avant/après ;
  tout changement déclare l'opération en échec. Si le mode liste
  blanche est détecté au départ, abandon sans aucune modification.
- **Déconnexion garantie** (`try/finally`), même après exception.
- **Délai global de 120 s** pour toute l'opération, en plus des
  timeouts HTTP existants.
- **Pré-vérification de joignabilité** : connexion TCP rapide (3 s)
  vers le routeur avant toute tentative, pour échouer vite hors du
  réseau domestique.
- **Erreurs structurées** : plus de traceback brut ; chaque échec
  produit un résultat explicite (JSON + code de sortie).

### Intégration Android (phase 2)

- **Sortie JSON par défaut** (contrat Tasker : `success`, `status`,
  `previous_status`, `requested_action`, `verified`, `message`,
  `error` le cas échéant, `changed` sur les succès), cohérente avec
  le code de sortie. Option `--format text` pour un usage humain.
- **Commande `status`** : lecture seule de l'état réel, aucune écriture.
- **Configuration par fichier** : `config.json` à côté du script
  (`router_ip`, `username`, `password`), prioritaire sur la constante
  `PASSWORD` (conservée vide par défaut pour compatibilité).
  `getpass` est supprimé : plus aucune saisie interactive, l'exécution
  Tasker est totalement non interactive.
- **Wrapper Tasker mis à jour** (`tasker/roblox_toggle`) : écrit le JSON
  dans `roblox_result.json` et le code de sortie dans
  `roblox_exit.txt` (la sortie d'erreur est isolée dans
  `roblox_result.err` pour ne jamais polluer le JSON).

### Qualité du dépôt (phase 3)

- Tests unitaires (`tests/`, `unittest` + `unittest.mock`, aucun
  routeur physique requis) couvrant authentification, lecture d'état,
  bascule, paramètres protégés et contrat Tasker.
- Intégration continue (`.github/workflows/tests.yml`) : tests sur
  Python 3.11 et 3.12 à chaque push et pull request.
- `config.example.json`, `requirements.txt`, `.gitignore`
  (dont `config.json`, pour ne jamais committer de mot de passe).
- `TROUBLESHOOTING.md`, guide Tasker (`tasker/README.md`) et README
  réécrit, avec note de migration v1 → v2.

### Protocole routeur : inchangé

Le protocole validé avec le ZTE F6600P n'a pas changé : chiffrement
RSA PKCS#1 v1.5 de l'en-tête `Check`, flux de login, lecture d'état
et écriture identiques à la v1. Seul `UrlFilterEnable` est écrit, les
autres paramètres étant repris tels quels. La liste des URL n'est
jamais touchée et aucun endpoint d'écriture de liste n'existe.
