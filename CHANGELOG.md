# Changelog — Plugin QGIS CEM NCVL

## v1.1.1 — Reste à faire en optique (GC)

### What's Changed
- Ajout du calcul du **reste optique** sur les GC produits (travaux faits).
- Nouveau **seuil paramétrable** `Reste optique`, par défaut à **50 ml**
  (sauvegardé via `QSettings`).
- Ajout des colonnes de linéaire GC **total**, **couvert** et **restant**
  (tableau + exports).
- Export **XLSX / SHP** enrichi pour les GC (`lgc_tot`, `lgc_couv`, `ml_rest`,
  `seuil_ml`, `motif`).
- Tests de non-régression sur les cas GC **partiellement couverts**.

Règle : un GC « travaux faits » ressort avec le motif `Reste à faire en
optique` lorsque `ML restant optique = longueur GC totale − longueur couverte
par câble tiré` est **strictement supérieur** au seuil. La couverture est
mesurée par échantillonnage le long du GC (union implicite, sans double
comptage) ; approximation documentée dans le README.

**Full Changelog**:
https://github.com/Pleymove/QD-CEM-NCVL/compare/v1.1.0...v1.1.1

## v1.1.0 — Analyse GC souterrain
- Nouvel onglet « Analyse GC souterrain » : GC `0_artere_gc` (travaux faits)
  sans câble tiré, rattachement spatial ligne↔ligne en EPSG:2154, exports
  XLSX et shapefile, filtre territoire.

## v1.0.x — Analyse poteaux
- 1.0.4 : champ `travaux` dans le tableau et les exports.
- 1.0.3 : UX retravaillée, zoom carte, export shapefile, filtre territoire.
- 1.0.2 : compatibilité PyQt6 / QGIS 4.
- 1.0.1 : compatibilité QGIS 4.x (`qgisMaximumVersion`).
- 1.0.0 : analyse poteaux remplacés/implantés sans câble tiré + dépôt QGIS.
