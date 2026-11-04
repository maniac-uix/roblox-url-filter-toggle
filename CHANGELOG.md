# Journal des modifications

## v2.0.0 — Fiabilisation (phases 1, 2 et 3 de l'audit du 2026-11-04)

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

### Correctifs (3e audit, avant publication de la v2.0.0)

- **Validation stricte des quatre paramètres avant toute écriture** :
  `UrlFilterEnable`, `UrlFilterTarget`, `MacFilterEnable` et
  `MacFilterTarget` doivent valoir strictement `0` ou `1`, sinon
  abandon sans aucune écriture (code 6, `STATE_READ_FAILED`) — une
  valeur vide ou inattendue (par exemple `MacFilterEnable=2`) ne peut
  plus être reprise dans le POST.
- **Tests cryptographiques** (`tests/test_crypto.py`) : structure du
  bloc PKCS#1 v1.5 (`00 02 || PS || 00 || message`, PS non nul de
  longueur exacte), en-tête `Check` (SHA-256 du body, RSA, Base64),
  longueurs de ciphertext (512 octets clé routeur) et rejet des
  messages trop longs.

### Correctifs (4e audit, avant publication de la v2.0.0)

- **Écriture atomique des résultats Tasker** : le wrapper écrit
  d'abord dans des fichiers temporaires, puis renomme (`mv` dans le
  même dossier) — Tasker ne lit jamais un fichier incomplet si
  l'exécution est interrompue pendant l'écriture.
- **Fichiers temporaires uniques (`mktemp`)** : chaque exécution du
  wrapper utilise ses propres fichiers temporaires — deux
  déclenchements rapprochés ne peuvent plus se marcher dessus (les
  noms fixes précédents étaient tronqués par le shell avant même
  que le verrou Python n'entre en jeu).
- **`requirements.txt` versionné** : `requests>=2.28,<3` pour une
  installation reproductible.

### Correctifs (6e audit, avant publication de la v2.0.0)

- **Version 2.0.0** : le README et le script annonçaient déjà
  « Version 2 » ; l'entrée du journal, elle, disait 1.0.0. La
  nouvelle version est 2.0.0 partout (`__version__`, `--version`,
  `pyproject.toml`, `SECURITY.md`, documentation).
- **Code de sortie 9 (`ROUTER_ERROR`)** : « routeur joignable mais
  réponse invalide » (réponse inattendue, erreur HTTP) sort
  désormais en code 9 au lieu du code 3, qui reste réservé à
  l'injoignable pur. **Changement de contrat** : mettre à jour
  toute tâche Tasker qui branchait sur le code 3 pour ce cas.
- **Permissions de `config.json`** : le chargement refuse tout
  fichier dont les droits dépassent `600` (test `mode & 0o077`) et
  renvoie `CONFIG_PERMISSIONS` (code 8) avec la commande de
  correction (`chmod 600 config.json`). Les modes propriétaire seul
  (`600`, `400`, …) restent acceptés. **Changement cassant** pour
  les installations existantes en `644`. Sous Termux, un
  `config.json` dans `~/storage` ne supporte pas `chmod` : le
  placer dans `~`.
- **`previous_status` dans les JSON d'erreur après écriture** :
  quand l'état avant écriture est connu, il est désormais inclus
  dans les erreurs survenant pendant ou après l'écriture (timeout,
  relecture impossible, état non confirmé) au lieu de `null`. Les
  erreurs avant lecture gardent `null`.
- **`--version` et `--help` sans dépendance** : les deux flags sont
  traités avant le test de présence de `requests` ; ils
  fonctionnent sans toucher au routeur et sans le module.
- **Aléatoire cryptographique** : le `rnd` anti-cache de la requête
  `login_token` utilise `secrets.token_hex(8)` (16 caractères hex)
  au lieu de `random` ; le padding PKCS#1 v1.5 est généré par une
  boucle `bytearray` propre (sans double `import os`).
- **Nettoyage HTTP** : retrait de tous les `verify=False` (inertes
  en HTTP local) et du `warnings.filterwarnings("ignore")` global.
- **Messages de joignabilité** : quand le routeur est injoignable,
  le message suggère explicitement « hors du réseau domestique ? ».
- **Documentation cœur du bouton** (`tasker/README.md`,
  `TROUBLESHOOTING.md`) : code 2 = succès (Branche 0/2 = succès),
  pas de relance automatique sur `AUTH_FAILED` (verrouillage du
  routeur), pattern anti-double-appui (deux widgets `on`/`off`),
  retour d'état via la commande `status`, alternative Termux:Widget,
  prérequis `allow-external-apps=true`, note sur la session admin
  du routeur, étapes d'export `.prj.xml` pour contribuer.
- **Limites connues** (README) : le filtre agit au niveau domaine
  et peut être contourné (VPN, données mobiles, DNS chiffré) ;
  tester sur chaque appareil avant de considérer le blocage comme
  acquis. Ces limites n'ont pas été testées sur chaque appareil.
- **Nouveaux fichiers du dépôt** : `install.sh` (installation
  Termux idempotente, sans jamais écraser ni créer `config.json`,
  sans toucher à `termux.properties` sans instruction affichée),
  `SECURITY.md`, modèles d'issues GitHub, `dependabot.yml` (pip,
  hebdomadaire), `pyproject.toml` (métadonnées, référence de la
  contrainte `requests>=2.28,<3`, alignée avec `requirements.txt`).
- **Crédits** : `juacas/zte_tracker` (GNU GPL v3) crédité comme
  référence protocolaire ; aucun code de ce projet n'a été copié.

### Protocole routeur : inchangé

Le protocole validé avec le ZTE F6600P n'a pas changé : chiffrement
RSA PKCS#1 v1.5 de l'en-tête `Check`, flux de login, lecture d'état
et écriture identiques à la v1. Seul `UrlFilterEnable` est écrit, les
autres paramètres étant repris tels quels. La liste des URL n'est
jamais touchée et aucun endpoint d'écriture de liste n'existe.
