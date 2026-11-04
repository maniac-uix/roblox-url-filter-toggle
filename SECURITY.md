# Politique de sécurité

## Version supportée

Seule la version **2.0.0** (branche `main`) reçoit des correctifs.

## Signaler un problème

Ouvrez une issue GitHub en décrivant le problème, sans jamais y
inclure de mot de passe, de jeton de session ni de capture contenant
des identifiants.

## Règles de base

- Le mot de passe admin du routeur ne doit **jamais** être commité
  dans Git, ni collé dans une issue : il vit uniquement dans
  `config.json`, sur l'appareil qui exécute le script, avec des
  droits `600` (`chmod 600 config.json`).
- L'administration du routeur ne doit **jamais** être exposée sur
  Internet : le script ne parle au routeur qu'en réseau local.
- Le script ne collecte ni n'envoie aucune donnée vers l'extérieur :
  tout se passe entre le téléphone et le routeur, en local.
