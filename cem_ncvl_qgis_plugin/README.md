# Plugin QGIS — CEM NCVL : Poteaux sans câble tiré

Plugin QGIS Python pour le projet **CEM NCVL**. Il identifie les **poteaux
remplacés / implantés** (famille `statut = 'plante'`) pour lesquels **aucun
câble rattaché spatialement n'est au statut « tiré »**, puis exporte un fichier
Excel détaillé avec synthèses.

Il répond au besoin client « poteaux implantés / remplacés sans câblage tiré »
sur l'ensemble du territoire CEM NCVL chargé dans QGIS (aucun filtre CVL ni
limite de date n'est imposé).

---

## 1. Installation

### Méthode manuelle (recommandée pour le MVP)

1. Copier le dossier `cem_ncvl_qgis_plugin/` dans le répertoire des extensions
   QGIS de l'utilisateur :
   - **Windows** :
     `C:\Users\<vous>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux** :
     `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS** :
     `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
2. Redémarrer QGIS.
3. Activer le plugin via **Extensions → Installer/Gérer les extensions →
   Installées**, puis cocher **CEM NCVL — Poteaux sans câble tiré**.
   (Le plugin étant marqué `experimental`, cocher *Afficher les extensions
   expérimentales* dans les paramètres si besoin.)

Une icône apparaît dans la barre d'outils et dans le menu **Extensions**.

### Prérequis

- **QGIS ≥ 3.16** (Python embarqué + `qgis.PyQt`).
- `openpyxl` est requis pour l'export XLSX. Il est généralement présent dans
  l'environnement Python de QGIS ; sinon l'installer via la console Python de
  QGIS :
  ```python
  import pip; pip.main(["install", "openpyxl"])
  ```

---

## 2. Couches attendues

| Rôle    | Couche CEM NCVL              | Géométrie         | CRS source |
| ------- | ---------------------------- | ----------------- | ---------- |
| Poteaux | `11_TRAVAUX_SUPPORTS.geom`   | Point             | EPSG:4326  |
| Câbles  | `0_cable_suivi.geom`         | (Multi)LineString | EPSG:2154  |

Les deux couches doivent être **ouvertes dans le projet QGIS**. Le plugin ne lit
que les couches du projet courant (pas de fichiers externes).

> Les noms de couches et de champs **ne sont jamais codés en dur** : le plugin
> propose des présélections intelligentes mais tout est modifiable dans
> l'interface.

---

## 3. Mapping des champs

### Onglet « Analyse poteaux »

| Champ                | Source  | Obligatoire | Présélection probable        |
| -------------------- | ------- | ----------- | ---------------------------- |
| Couche poteaux       | —       | Oui         | `11_TRAVAUX_SUPPORTS.geom`   |
| Couche câbles        | —       | Oui         | `0_cable_suivi.geom`         |
| ID poteau            | Poteaux | Oui         | `num_appui` / `id`           |
| État poteau          | Poteaux | Oui         | `statut`                     |
| Statut câble         | Câbles  | Oui         | `statut`                     |
| Référence câble      | Câbles  | Non         | `ref_cable`                  |
| Commune              | Poteaux | Non         | `commune`                    |
| Département          | Poteaux | Non         | `departement` / `dept`       |
| Territoire / plaque  | Poteaux | Non         | `code_imputation` / `region` |

Le bouton **Tester les couches / champs** vérifie les couches, compte les
entités et alimente les deux multi-sélections (états poteau, statuts câble) à
partir des valeurs réellement présentes dans les couches.

---

## 4. Méthode d'analyse

Il n'existe **pas de champ commun fiable** entre la couche câble et la couche
supports : le rattachement est donc **purement spatial**.

1. **Filtre poteau** : seuls les poteaux dont l'état est coché sont analysés.
   Par défaut, la famille `plante` (planté / remplacé / recalé) est cochée.
2. **Reprojection** : poteaux et câbles sont reprojetés en **EPSG:2154** (CRS
   métrique), seul CRS où un buffer en mètres a un sens.
3. **Buffer** : autour de chaque poteau, un rayon de recherche **paramétrable**
   (par défaut **5 m**) définit la zone de rattachement.
4. **Rattachement** : un câble est associé au poteau si sa géométrie passe à une
   distance ≤ rayon du poteau.
5. **Règle de sortie** : le poteau ressort si **aucun** câble rattaché n'a un
   statut « tiré ».

### Statuts « tirés » par défaut

`Tiré` et `Tirage fini` sont cochés par défaut, mais la liste est **modifiable**
via la multi-sélection des statuts détectés dans la couche câble. La comparaison
est faite sur des valeurs normalisées (espaces / casse ignorés) tout en
conservant les libellés source à l'export.

### Motifs de sortie

| Situation                                            | Sort ? | Motif                          |
| ---------------------------------------------------- | ------ | ------------------------------ |
| Poteau retenu + aucun câble dans le buffer           | Oui    | `Aucun câble associé`          |
| Poteau retenu + câbles présents mais aucun tiré      | Oui    | `Aucun câble au statut tiré`   |
| Poteau retenu + au moins un câble tiré               | Non    | —                              |
| Poteau hors états sélectionnés                       | Non    | —                              |

### Compteurs affichés

Poteaux analysés · poteaux remplacés / implantés · câbles analysés · poteaux
sans câble tiré · nombre de statuts câble distincts.

---

## 5. Export XLSX

Onglet **Récap TCD / export → Exporter XLSX**. Le fichier contient cinq
feuilles :

| Feuille          | Contenu                                                        |
| ---------------- | ------------------------------------------------------------- |
| `Paramètres`     | Date, couches, champs, filtres et compteurs de l'analyse      |
| `Liste poteaux`  | Détail des poteaux sortis (table structurée, filtres, gel)    |
| `Câbles associés`| Détail des câbles rattachés aux poteaux sortis + distance     |
| `Synthèse`       | Récaps par territoire / département / commune / état / motif   |
| `TCD`            | Table à plat agrégée prête à pivoter (Tableau croisé dynamique)|

Les feuilles de détail ont en-têtes figés, auto-filtres Excel, tables
structurées et colonnes ajustées, pour une exploitation directe.

---

## 6. Architecture

```
cem_ncvl_qgis_plugin/
├─ metadata.txt            # déclaration QGIS
├─ __init__.py             # classFactory
├─ cem_ncvl_plugin.py      # intégration QGIS (menu, action)
├─ qgis_adapter.py         # seul module métier qui importe QGIS
├─ ui/
│  └─ main_dialog.py       # interface à onglets (qgis.PyQt)
├─ core/                   # logique métier pure (testable sans QGIS)
│  ├─ normalize.py
│  ├─ geometry.py          # distances point/ligne + grille spatiale
│  ├─ models.py            # Pole / Cable
│  ├─ layer_mapping.py     # présélection intelligente couches/champs
│  ├─ cable_filters.py     # statuts « tirés »
│  ├─ poteaux_analysis.py  # règle métier principale
│  ├─ synthese.py          # synthèses + table TCD
│  ├─ columns.py           # définition des colonnes
│  └─ export_xlsx.py       # génération du classeur Excel
├─ resources/icon.svg
├─ tests/                  # tests pytest de la logique métier
└─ README.md
```

Séparation stricte **interface / métier / export**. La logique d'analyse, de
synthèse et d'export ne dépend pas de QGIS et est couverte par des tests.

Le mapping (couches, champs, buffer) est **sauvegardé via `QSettings`** et
rechargé à l'ouverture suivante.

---

## 7. Tests

Les tests portent sur la logique métier (`core`) et s'exécutent dans un Python
standard, sans QGIS :

```bash
pip install -r requirements-dev.txt
pytest
```

---

## 8. Limites connues

- Le rattachement spatial dépend de la qualité et du géoréférencement des
  couches ; un buffer trop large peut rattacher des câbles voisins non
  pertinents (ajuster le rayon).
- Le calcul charge les géométries en mémoire : sur de très gros jeux, prévoir
  un filtrage préalable (emprise / sélection) dans QGIS.
- L'export utilise une table « prête à pivoter » plutôt qu'un TCD natif Excel
  (choix volontaire pour la robustesse, cf. brief).
- La détermination « remplacé / implanté » repose sur le champ d'état choisi
  (`statut = 'plante'` par défaut). Adapter la sélection si le projet utilise
  une autre convention (champ `travaux`, etc.).
