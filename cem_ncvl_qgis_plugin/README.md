# Plugin QGIS — CEM NCVL : Poteaux sans câble tiré

Plugin QGIS Python pour le projet **CEM NCVL**. Il identifie les **poteaux
remplacés / implantés** (famille `statut = 'plante'`) pour lesquels **aucun
câble rattaché spatialement n'est au statut « tiré »**, puis exporte un fichier
Excel détaillé avec synthèses.

Il répond au besoin client « poteaux implantés / remplacés sans câblage tiré »
sur l'ensemble du territoire CEM NCVL chargé dans QGIS (aucun filtre CVL ni
limite de date n'est imposé).

Depuis la **1.1.0**, le plugin gère aussi un second cas client via l'onglet
**Analyse GC souterrain** : les **artères GC dont les travaux sont faits** mais
sans câble tiré (voir section dédiée plus bas).

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
| Travaux              | Poteaux | Non         | `travaux`                    |
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

### Filtre territoire / plaque

En plus des états poteau et des statuts câble, une troisième multi-sélection
permet de **restreindre l'analyse à un ou plusieurs territoires / plaques**
(valeurs issues du champ « Territoire / plaque »). Laisser la liste vide =
analyser tous les territoires.

### Tableau interactif

- **Filtre texte** au-dessus du tableau (ID, commune, motif…).
- **Tri** par clic sur les en-têtes de colonnes.
- **Zoom carte** : sélectionner une ligne puis cliquer **Zoomer sur le poteau**
  (ou double-cliquer la ligne) → QGIS centre et fait clignoter le poteau.
- **Exporter poteaux (SHP)** : génère un **shapefile** ponctuel (EPSG:2154) des
  poteaux sortis, avec les colonnes d'analyse, et l'ajoute au projet QGIS.

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

## 5 bis. Analyse GC souterrain (onglet dédié)

Second cas client : identifier les **artères de génie civil souterrain dont les
travaux sont faits** mais pour lesquelles **aucun câble rattaché n'est tiré**.

| Rôle    | Couche CEM NCVL      | Géométrie         | CRS    |
| ------- | -------------------- | ----------------- | ------ |
| GC      | `0_artere_gc`        | (Multi)LineString | 2154   |
| Câbles  | `0_cable_suivi.geom` | (Multi)LineString | 2154   |

**Mapping GC** (présélections intelligentes) : ID GC `id_0`, nom / code GC
`nom` (sinon l'ID), suivi travaux `suivi_pilotage`, plaque `plaque`, commune
`commune`, longueur `ml_calc`/`ml`.

**Règle métier (depuis la 1.1.1 — reste à faire en optique)** :
1. ne retenir que les GC « travaux faits » (par défaut `suivi_pilotage` ∈
   {`TRX fini`, `facturation`}, modifiable) ;
2. rattacher les câbles par **intersection / proximité ligne↔ligne** en
   EPSG:2154, avec une **tolérance paramétrable** (par défaut **1 m**) ;
3. calculer le **linéaire restant sans optique** :
   `ML restant optique = longueur GC totale − longueur couverte par câble tiré` ;
4. sortir le GC (motif **`Reste à faire en optique`**) si ce reste est
   **strictement supérieur** au **seuil paramétrable** (`Seuil reste optique`,
   **50 ml** par défaut, sauvegardé via `QSettings`).

> Un câble **non tiré** ne « couvre » pas optiquement le GC ; seuls les câbles
> aux statuts tirés (`Tiré`, `Tirage fini`) réduisent le reste. Un GC sans
> câble (ou sans câble tiré) ressort donc dès que sa longueur dépasse le seuil.

**Calcul de la longueur couverte (approximation documentée)** : la couverture
est mesurée par **échantillonnage** le long du GC (pas ≈ 2 m). Chaque
sous-segment est compté couvert si son milieu est à ≤ tolérance d'un câble
tiré. Le test étant binaire par sous-segment, l'**union est implicite** : pas
de **double comptage** quand plusieurs câbles se superposent. La précision est
de l'ordre du pas d'échantillonnage. La longueur totale est calculée sur la
géométrie reprojetée en EPSG:2154 (cohérente avec la couverture).

**Colonnes ajoutées** : `Longueur GC totale (m)`, `Longueur couverte optique
(m)`, `ML restant optique (m)`, `Seuil reste optique (ml)`, et le motif.

**Restitutions** : tableau dédié (zoom carte, tri/filtre), **export shapefile**
linéaire des GC sortis (champs `lgc_tot`, `lgc_couv`, `ml_rest`, `seuil_ml`,
`motif`…), et **export XLSX** (feuilles `Paramètres`, `GC souterrains`,
`Câbles associés`, `Synthèse`, `TCD`).

---

## 6. Architecture

```
cem_ncvl_qgis_plugin/
├─ metadata.txt            # déclaration QGIS
├─ __init__.py             # classFactory
├─ cem_ncvl_plugin.py      # intégration QGIS (menu, action)
├─ qgis_adapter.py         # seul module métier qui importe QGIS
├─ ui/
│  ├─ main_dialog.py       # fenêtre à onglets (qgis.PyQt)
│  └─ gc_tab.py            # onglet « Analyse GC souterrain »
├─ core/                   # logique métier pure (testable sans QGIS)
│  ├─ normalize.py
│  ├─ geometry.py          # distances point/ligne, ligne/ligne + grille
│  ├─ models.py            # Pole / Cable / GcArtere
│  ├─ layer_mapping.py     # présélection intelligente couches/champs
│  ├─ cable_filters.py     # statuts « tirés »
│  ├─ poteaux_analysis.py  # règle métier poteaux
│  ├─ gc_analysis.py       # règle métier GC souterrain
│  ├─ synthese.py          # synthèses + table TCD
│  ├─ columns.py           # définition des colonnes (poteaux + GC)
│  └─ export_xlsx.py       # génération des classeurs Excel
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
