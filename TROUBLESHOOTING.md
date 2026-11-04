# Dépannage

Chaque erreur produit un JSON avec un champ `error` et un code de
sortie (écrit par le wrapper dans `roblox_exit.txt`). Retrouvez le
cas ci-dessous.

## Routeur injoignable — `ROUTER_UNREACHABLE` (code 3)

- Vérifiez que le téléphone est bien sur le **WiFi de la maison**
  (pas en données mobiles, pas sur un autre réseau).
- Vérifiez que le routeur est allumé et joignable à son adresse
  (par défaut `192.168.11.1`, modifiable dans `config.json`).
- Si l'adresse du routeur a changé, mettez à jour `router_ip`
  dans `config.json`.

## Authentification refusée — `AUTH_FAILED` (code 4)

- Le mot de passe admin est faux : corrigez `password` dans
  `config.json` (ou la constante `PASSWORD` du script).
- Si le routeur affiche un verrouillage (trop de tentatives),
  attendez la fin du verrouillage avant de réessayer.
- **Ne jamais relancer automatiquement sur `AUTH_FAILED`** : le
  routeur verrouille après plusieurs échecs (`lockingTime`), et
  chaque nouvelle tentative prolonge le verrouillage. Corrigez le
  mot de passe d'abord, puis relancez une seule fois à la main. Le
  script ne contient d'ailleurs aucune logique de retry : chaque
  exécution ne tente qu'une seule authentification.
- Vérifiez aussi `username` (par défaut `user`).

## Routeur joignable mais réponse invalide — `ROUTER_ERROR` (code 9)

- Le routeur répond, mais sa réponse est invalide ou inattendue
  (par exemple erreur HTTP sur une requête). Ce n'est **pas** un
  problème de réseau : ne pas confondre avec `ROUTER_UNREACHABLE`
  (code 3, routeur injoignable).
- Vérifiez que l'interface web du routeur répond normalement, puis
  réessayez une fois. Si le problème persiste, notez la réponse du
  routeur et signalez-le (voir `SECURITY.md` pour ce qu'il ne faut
  jamais inclure : aucun mot de passe, aucun jeton).

## Écriture refusée — `WRITE_FAILED` (code 5)

- Le routeur a refusé l'écriture (session expirée, jeton invalide).
  Réessayez une fois : le script redemande un jeton frais à chaque
  écriture.
- Si le problème persiste, rouvrez l'interface web du routeur
  (Critères de filtrage) pour vérifier que la session web n'est pas
  bloquée, puis réessayez.

## État final non confirmé — `STATE_NOT_CONFIRMED` (code 6)

- Le routeur a répondu favorablement mais la relecture ne confirme
  pas le nouvel état, ou la réponse d'écriture a été perdue.
- **Ne cliquez pas frénétiquement** : ouvrez l'interface web du
  routeur (Critères de filtrage) et vérifiez l'état réel avant toute
  nouvelle tentative. Le script ne bascule jamais à l'aveugle.
- Si l'état réel correspond à ce que vous vouliez, tout va bien :
  seule la confirmation automatique a échoué.

## Paramètres protégés modifiés — `PROTECTED_PARAMS_CHANGED` (code 6)

- Après écriture, le mode (`UrlFilterTarget`) ou le filtre MAC a
  changé par rapport à l'état initial. L'opération est déclarée en
  échec par sécurité.
- Vérifiez dans l'interface du routeur que le mode est toujours
  **Liste noire** et que le filtre MAC est dans son état habituel,
  puis réessayez. Ne modifiez jamais la liste des URL à la main
  pendant une bascule.

## Valeur de paramètre invalide — `STATE_READ_FAILED` (code 6)

- L'un des quatre paramètres lus (`UrlFilterEnable`, `UrlFilterTarget`,
  `MacFilterEnable`, `MacFilterTarget`) est absent, vide ou ne vaut
  pas `0` ou `1` (par exemple `MacFilterEnable=2`). Le script abandonne
  **sans aucune écriture**, comme pour un paramètre absent.
- Vérifiez dans l'interface du routeur (Critères de filtrage) que les
  paramètres sont bien renseignés et cohérents, puis réessayez. Ne
  forcez jamais une bascule tant que la lecture n'est pas propre.

## Exécution déjà en cours — `ALREADY_RUNNING` (code 7)

- Un lancement précédent n'est pas encore terminé. Attendez
  quelques secondes et réessayez. Le verrou se libère seul à la fin
  de l'exécution (ou si le processus meurt).
- Si le verrou semble bloqué durablement (aucune exécution en
  cours), supprimez le fichier `roblox_toggle.lock` du répertoire
  temporaire de Termux et réessayez.

## Configuration invalide — `INVALID_CONFIG`, `PASSWORD_NOT_CONFIGURED`, `CONFIG_PERMISSIONS` (code 8)

- `PASSWORD_NOT_CONFIGURED` : aucun mot de passe disponible. Copiez
  `config.example.json` vers `config.json` à côté du script,
  renseignez `password`, puis `chmod 600 config.json`.
- `INVALID_CONFIG` : `config.json` est illisible ou n'est pas un
  objet JSON valide. Corrigez sa syntaxe (virgules, guillemets).
- `CONFIG_PERMISSIONS` : `config.json` a des droits trop ouverts
  (groupe ou autres autorisés). Le script refuse de démarrer tant
  que les droits ne sont pas resserrés : `chmod 600 config.json`.
  Seuls les modes propriétaire seul sont acceptés (`600`, `400`,
  …). **Changement cassant** : une installation existante en
  `644` doit resserrer ses droits avant de redémarrer. Sous Termux,
  ne placez pas `config.json` dans `~/storage` : le stockage
  partagé Android ne supporte pas `chmod`, placez-le dans `~`.
- `INVALID_USAGE` : argument inconnu. Usages valides : `on`, `off`,
  `toggle`, `status`, `--format json|text`, `--help`, `--version`.

## Session admin du routeur pendant une bascule

- Comportement **non testé** si l'interface web du routeur est
  ouverte pendant une bascule, ou si un logout échoue : par
  prudence, évitez d'utiliser l'interface web pendant une bascule.
- Le script tente toujours le logout en fin d'exécution (`finally`)
  ; un échec de logout est ignoré par conception et ne change pas
  le résultat de l'opération.

## Liste blanche détectée — `WHITELIST_DETECTED` (code 8)

- Le routeur est en mode **liste blanche** au lieu de liste noire.
  Le script abandonne **sans rien modifier**, pour ne pas risquer
  de perturber la configuration.
- Remettez le mode sur **Liste noire** dans l'interface du routeur
  (Critères de filtrage), vérifiez que la liste noire Roblox est
  toujours en place, puis réessayez.

## Délai dépassé — `TIMEOUT` (code 3 ou 6)

- L'opération a dépassé 120 s. Code 3 si rien n'a encore été écrit,
  code 6 si une écriture a pu avoir lieu (état incertain : vérifiez
  l'interface du routeur avant de réessayer).
- Cause fréquente : WiFi faible ou routeur très lent à répondre.

## Tasker affiche du JSON au lieu d'un message

- C'est le comportement normal de la v2 : la sortie est du JSON.
  La tâche Tasker doit analyser `roblox_result.json` (action
  **JSON Read** ou JavaScriptlet `JSON.parse`) et afficher
  `message`, pas le contenu brut du fichier. Voir
  `tasker/README.md`.
- Pour un test manuel lisible, lancez le script avec
  `--format text`.

## Le module `requests` est introuvable — `MISSING_DEPENDENCY` (code 8)

- Dans Termux : `pip install requests` (ou `pip install -r
  requirements.txt` depuis le dépôt), puis réessayez.
