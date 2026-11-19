# MyoTools v0.5.0 — Windows

Cette archive contient les quatre applications et tous les fichiers communs
nécessaires à ce système. Vous n'avez besoin ni de l'autre archive ni du dépôt complet.
Conservez ensemble tous les fichiers et dossiers extraits.

1. Extrayez entièrement le ZIP dans le dossier où vous souhaitez conserver MyoTools.
2. Lancez `INSTALL.bat` depuis ce dossier pour installer MyoTools et créer le raccourci bureau.
3. Ouvrez le raccourci bureau, ou lancez `LAUNCH.bat`.

L'installation nécessite Internet et de l'espace disque pour Conda, PyTorch et les
autres dépendances. L'installateur utilise une distribution Conda existante ou
installe Miniforge si nécessaire. Les environnements Conda ne sont pas intégrés au ZIP.

Les images sont recherchées par défaut sur votre Bureau. Vous pouvez sélectionner
un autre dossier dans chaque application. Dans le hub, ouvrez **Models** pour
télécharger et vérifier les modèles des releases ; les chemins sont ensuite
proposés dans MyoSeg, MyoClass et MyoFuse. Le modèle Svetlana est téléchargé
par l'installateur. MyoSurface ne nécessite pas de modèle externe. Les modèles
restent hors de cette archive et ne sont pas effacés par la désinstallation.

## Closing MyoTools

Opening this installation again reopens its existing Hub. Select **Quit MyoTools**
in the Hub to stop it. If applications are still running, save your work and
confirm before closing them. Closing the browser tab alone leaves the Hub running.

## Guides d'utilisation

- [MyoSeg](MyoSeg/MyoSeg_How_to_Use.md) : fluorescence, H&E et morphométrie.
- [MyoClass](MyoClass/MyoClass_How_to_Use.md) : typage, Napari et exports.
- [MyoFuse](MyoFuse/MyoFuse_How_to_Use.md) : modèles, fusion et reprise.
- [MyoSurface](MyoSurface/MyoSurface_How_to_Use.md) : seuil, surface et CSV.

## Désinstallation

Utilisez « Uninstall MyoTools » sur la landing page, ou lancez `UNINSTALL.bat`.
La confirmation demandée est `UNINSTALL MYOTOOLS`. Seuls les environnements dont
l'appartenance à cette installation est prouvée et le raccourci correspondant
peuvent être supprimés. Anaconda/Miniforge et les données scientifiques sont conservés.
Conservez le dossier d'installation à son emplacement pendant son utilisation.

## Versions incluses

| Application | Version |
| --- | --- |
| MyoSeg | 1.2.0 |
| MyoClass | 1.0.3 |
| MyoFuse | 1.1.3 |
| MyoSurface | 1.0.0 |

During use, diagnostic messages appear in the launch terminal and in `Hub/runtime/<application>.log`. Each application log is replaced when the application is launched again. Logs can contain file names and paths; review them before sharing.
Il s'agit de la distribution de MyoTools v0.5.0 ; voir `DISTRIBUTION.json` pour la référence source.
