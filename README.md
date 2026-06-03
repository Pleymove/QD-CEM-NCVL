# QD-CEM-NCVL

Plugin QGIS pour le projet **CEM NCVL** : analyse des **poteaux remplacés /
implantés sans câble tiré**.

Le plugin filtre les poteaux de la couche supports (`11_TRAVAUX_SUPPORTS.geom`,
`statut = 'plante'`), rattache **spatialement** les câbles
(`0_cable_suivi.geom`) via un buffer paramétrable (5 m par défaut, EPSG:2154),
et liste les poteaux dont aucun câble rattaché n'est au statut « tiré »
(`Tiré`, `Tirage fini` par défaut). Il produit un export Excel détail +
synthèses.

## Installation dans QGIS (dépôt d'extensions)

Le plugin se distribue comme un **dépôt d'extensions QGIS personnalisé** : on
ajoute **une seule fois** l'URL du dépôt, puis QGIS gère l'installation et les
**mises à jour**.

1. QGIS → **Extensions → Installer/Gérer les extensions → Paramètres**.
2. Section **Dépôts d'extensions → Ajouter…**
   - **Nom** : `CEM NCVL`
   - **URL** :
     `https://raw.githubusercontent.com/Pleymove/QD-CEM-NCVL/main/plugins.xml`
3. Onglet **Toutes** → rechercher *CEM NCVL* → **Installer le plugin**.
4. À chaque nouvelle release, QGIS affiche **« Mettre à jour »**.

> ⚠️ Pour que cette URL fonctionne, deux actions manuelles côté mainteneur sont
> nécessaires (voir [section release](#publier-une-version-pour-le-dépôt)) :
> **merger la PR sur `main`** (pour publier `plugins.xml`) puis **créer une
> release GitHub** (qui génère et attache automatiquement le ZIP du plugin).

## Démarrage

- **Code du plugin** : [`cem_ncvl_qgis_plugin/`](cem_ncvl_qgis_plugin/)
- **Documentation complète** (installation, mapping, méthode, export) :
  [`cem_ncvl_qgis_plugin/README.md`](cem_ncvl_qgis_plugin/README.md)

## Développement / tests

La logique métier (`cem_ncvl_qgis_plugin/core/`) est indépendante de QGIS et
couverte par des tests exécutables dans un Python standard :

```bash
pip install -r requirements-dev.txt
pytest
```

## Publier une version pour le dépôt

Le dépôt d'extensions repose sur trois éléments :

- `plugins.xml` (racine) : flux lu par QGIS. Son `<version>` doit **toujours**
  être identique à `version=` dans `cem_ncvl_qgis_plugin/metadata.txt`.
- `.github/workflows/release.yml` : à chaque **release publiée**, zippe le
  dossier `cem_ncvl_qgis_plugin/` et attache `cem_ncvl_qgis_plugin.zip` à la
  release. Le `download_url` de `plugins.xml` pointe vers
  `releases/latest/download/…` → il ne change jamais.
- Une **release GitHub** par version.

Procédure pour publier la **V1** (et toute version ultérieure) :

1. Vérifier que `version=` (metadata.txt) et `<version>` (plugins.xml) sont
   identiques (ex. `1.0.0`).
2. **Merger la PR sur `main`** (manuellement, depuis GitHub).
3. Créer une **release GitHub** avec le tag `v1.0.0`. L'Action génère et
   attache automatiquement `cem_ncvl_qgis_plugin.zip`.
4. QGIS détecte l'extension / la mise à jour au prochain rafraîchissement du
   dépôt (le cache `raw.githubusercontent.com` peut mettre ~5 min).

Pour une mise à jour : bumper le numéro dans `metadata.txt` **et**
`plugins.xml`, merger, puis créer une nouvelle release `vX.Y.Z`.

## Licence

Usage interne Pleymove / CEM NCVL.
