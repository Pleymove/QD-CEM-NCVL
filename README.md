# QD-CEM-NCVL

Plugin QGIS pour le projet **CEM NCVL** : analyse des **poteaux remplacés /
implantés sans câble tiré**.

Le plugin filtre les poteaux de la couche supports (`11_TRAVAUX_SUPPORTS.geom`,
`statut = 'plante'`), rattache **spatialement** les câbles
(`0_cable_suivi.geom`) via un buffer paramétrable (5 m par défaut, EPSG:2154),
et liste les poteaux dont aucun câble rattaché n'est au statut « tiré »
(`Tiré`, `Tirage fini` par défaut). Il produit un export Excel détail +
synthèses.

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

## Licence

Usage interne Pleymove / CEM NCVL.
