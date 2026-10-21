# MyoTools v0.4.1 — Linux

Cette archive contient les quatre applications et tous les fichiers communs
nécessaires à ce système. Vous n'avez besoin ni de l'autre archive ni du dépôt complet.
Conservez ensemble tous les fichiers et dossiers extraits.

1. Extrayez entièrement le ZIP dans le dossier où vous souhaitez conserver MyoTools.
2. Lancez `bash INSTALL.sh` depuis ce dossier pour installer MyoTools et créer le raccourci bureau.
3. Ouvrez le raccourci bureau, ou lancez `bash LAUNCH.sh`.

L'installation nécessite Internet et de l'espace disque pour Conda, PyTorch et les
autres dépendances. L'installateur utilise une distribution Conda existante ou
installe Miniforge si nécessaire. Les environnements Conda ne sont pas intégrés au ZIP.

Les images sont recherchées par défaut sur votre Bureau. Vous pouvez sélectionner
un autre dossier dans chaque application. Dans le hub, ouvrez **Models** pour
télécharger et vérifier les modèles des releases ; les chemins sont ensuite
proposés dans MyoSeg, MyoClass et MyoFuse. Le modèle Svetlana est téléchargé
par l'installateur. MyoSurface ne nécessite pas de modèle externe. Les modèles
restent hors de cette archive et ne sont pas effacés par la désinstallation.

## Guides d'utilisation

- [MyoSeg](MyoSeg/MyoSeg_How_to_Use.md) : fluorescence, H&E et morphométrie.
- [MyoClass](MyoClass/MyoClass_How_to_Use.md) : typage, Napari et exports.
- [MyoFuse](MyoFuse/MyoFuse_How_to_Use.md) : modèles, fusion et reprise.
- [MyoSurface](MyoSurface/MyoSurface_How_to_Use.md) : seuil, surface et CSV.

## Désinstallation

Utilisez « Uninstall MyoTools » sur la landing page, ou lancez `bash UNINSTALL.sh`.
La confirmation demandée est `UNINSTALL MYOTOOLS`. Seuls les environnements dont
l'appartenance à cette installation est prouvée et le raccourci correspondant
peuvent être supprimés. Anaconda/Miniforge et les données scientifiques sont conservés.
Conservez le dossier d'installation à son emplacement pendant son utilisation.

## Versions incluses

| Application | Version |
| --- | --- |
| MyoSeg | 1.1.1 |
| MyoClass | 1.0.1 |
| MyoFuse | 1.1.0 |
| MyoSurface | 1.0.0 |

En cas d'erreur, consultez la fenêtre de terminal et les journaux dans `Hub/runtime/`.
Il s'agit de la distribution de MyoTools v0.4.1 ; voir `DISTRIBUTION.json` pour la référence source.
