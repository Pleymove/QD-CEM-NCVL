"""Fenêtre principale du plugin CEM NCVL — interface à onglets.

Onglet 1 « Analyse poteaux » : sélection des couches, mapping des champs,
test, filtres multi-sélection (état poteau / statut câble tiré / territoire),
buffer, analyse, tableau résultat avec zoom carte et export shapefile.

Onglet 2 « Récap TCD / export » : synthèses calculées et export XLSX.

L'interface ne porte aucune logique métier : elle prépare les données via
``qgis_adapter`` puis délègue à ``core`` (analyse, synthèses, export).
"""

import os

from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSplitter,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from .. import qgis_adapter as adapter
from ..core import layer_mapping
from ..core.cable_filters import DEFAULT_PULLED_STATUSES
from ..core.columns import POLE_COLUMNS
from ..core.poteaux_analysis import analyze, DEFAULT_BUFFER_M, DEFAULT_POLE_STATES
from ..core.synthese import build_syntheses
from ..core import export_xlsx
from ..core.normalize import normalize_status

SETTINGS_PREFIX = "cem_ncvl_plugin/"


class CemNcvlDialog(QDialog):
    """Dialogue principal du plugin."""

    def __init__(self, iface=None, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.settings = QSettings()

        self.poles = []
        self.cables = []
        self.rows = []
        self.counters = {}
        self.cable_detail = []
        self._visible_rows = []          # lignes actuellement affichées (filtre)
        self._analysis_pole_layer = None  # couche source pour le zoom carte

        self.setWindowTitle("CEM NCVL — Poteaux sans câble tiré")
        self.resize(1040, 760)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_tab_analyse(), "Analyse poteaux")
        self.tabs.addTab(self._build_tab_recap(), "Récap TCD / export")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self._reload_layers()
        self._load_settings()

    # ------------------------------------------------------------ UI helpers
    def _build_checklist_column(self, title, tooltip=""):
        """Construit une colonne « titre + boutons Tout/Rien + liste cochable »."""
        col = QVBoxLayout()
        label = QLabel(title)
        if tooltip:
            label.setToolTip(tooltip)
        col.addWidget(label)

        buttons = QHBoxLayout()
        btn_all = QPushButton("Tout")
        btn_none = QPushButton("Rien")
        for btn in (btn_all, btn_none):
            btn.setMaximumWidth(60)
        buttons.addWidget(btn_all)
        buttons.addWidget(btn_none)
        buttons.addStretch()
        col.addLayout(buttons)

        widget = QListWidget()
        widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        col.addWidget(widget)

        btn_all.clicked.connect(lambda: self._set_all_checks(widget, True))
        btn_none.clicked.connect(lambda: self._set_all_checks(widget, False))
        return col, widget

    def _set_all_checks(self, widget, checked):
        state = (Qt.CheckState.Checked if checked
                 else Qt.CheckState.Unchecked)
        for i in range(widget.count()):
            widget.item(i).setCheckState(state)

    # ------------------------------------------------------------------ UI
    def _build_tab_analyse(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)

        splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(splitter)

        # ============ Zone configuration (défilable) ============
        config = QWidget()
        cfg = QVBoxLayout(config)

        cfg.addWidget(self._build_box_layers())
        cfg.addWidget(self._build_box_filters())

        btn_analyse = QPushButton("Analyser")
        btn_analyse.setMinimumHeight(34)
        btn_analyse.setStyleSheet("font-weight: bold;")
        btn_analyse.clicked.connect(self.on_analyse)
        cfg.addWidget(btn_analyse)

        self.lbl_counters = QLabel("Aucune analyse lancée.")
        self.lbl_counters.setWordWrap(True)
        self.lbl_counters.setStyleSheet("font-weight: bold; color: #1F4E78;")
        cfg.addWidget(self.lbl_counters)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(config)
        splitter.addWidget(scroll)

        # ============ Zone résultats ============
        splitter.addWidget(self._build_results_widget())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 360])
        return tab

    def _build_box_layers(self):
        box = QGroupBox("1. Couches et champs")
        form = QFormLayout(box)

        self.cmb_pole_layer = QComboBox()
        self.cmb_cable_layer = QComboBox()
        self.cmb_pole_layer.currentIndexChanged.connect(self._on_pole_layer)
        self.cmb_cable_layer.currentIndexChanged.connect(self._on_cable_layer)

        btn_reload = QPushButton("Recharger les couches")
        btn_reload.clicked.connect(self._reload_layers)
        row_pole = QHBoxLayout()
        row_pole.addWidget(self.cmb_pole_layer)
        row_pole.addWidget(btn_reload)
        wrap_pole = QWidget()
        wrap_pole.setLayout(row_pole)

        form.addRow("Couche poteaux *", wrap_pole)
        form.addRow("Couche câbles *", self.cmb_cable_layer)

        self.cmb_id_poteau = QComboBox()
        self.cmb_etat_poteau = QComboBox()
        self.cmb_travaux = QComboBox()
        self.cmb_ref_cable = QComboBox()
        self.cmb_statut_cable = QComboBox()
        self.cmb_commune = QComboBox()
        self.cmb_departement = QComboBox()
        self.cmb_territoire = QComboBox()

        self.cmb_id_poteau.setToolTip("Champ identifiant du poteau (ex. num_appui)")
        self.cmb_etat_poteau.setToolTip("Champ d'état (ex. statut = 'plante')")
        self.cmb_statut_cable.setToolTip("Champ de statut du câble")
        self.cmb_travaux.setToolTip(
            "Champ « travaux » du support (ex. A poser, Remplacement…) — "
            "affiché dans le tableau et les exports")
        self.cmb_territoire.setToolTip(
            "Champ territoire / plaque (sert au filtre et aux synthèses)")

        form.addRow("ID poteau *", self.cmb_id_poteau)
        form.addRow("État poteau *", self.cmb_etat_poteau)
        form.addRow("Travaux", self.cmb_travaux)
        form.addRow("Référence câble", self.cmb_ref_cable)
        form.addRow("Statut câble *", self.cmb_statut_cable)
        form.addRow("Commune", self.cmb_commune)
        form.addRow("Département", self.cmb_departement)
        form.addRow("Territoire / plaque", self.cmb_territoire)

        self.spin_buffer = QDoubleSpinBox()
        self.spin_buffer.setRange(0.1, 1000.0)
        self.spin_buffer.setDecimals(1)
        self.spin_buffer.setSingleStep(0.5)
        self.spin_buffer.setValue(DEFAULT_BUFFER_M)
        self.spin_buffer.setSuffix(" m")
        self.spin_buffer.setToolTip(
            "Rayon du buffer autour du poteau (analyse en EPSG:2154)")
        form.addRow("Rayon de recherche autour du poteau", self.spin_buffer)

        btn_test = QPushButton("Tester les couches / champs")
        btn_test.setToolTip(
            "Valide le mapping et charge les valeurs des filtres ci-dessous")
        btn_test.clicked.connect(self.on_test)
        form.addRow(btn_test)
        return box

    def _build_box_filters(self):
        box = QGroupBox("2. Filtres métier (cliquer « Tester » pour les remplir)")
        h = QHBoxLayout(box)

        col_pole, self.list_pole_states = self._build_checklist_column(
            "États poteau à analyser",
            "Cas client : famille « plante » (planté / remplacé / recalé)")
        col_pulled, self.list_pulled = self._build_checklist_column(
            "Statuts câble « tirés »",
            "Un poteau sort si aucun câble rattaché n'a un de ces statuts")
        col_terr, self.list_territoires = self._build_checklist_column(
            "Territoire / plaque",
            "Laisser vide = analyser tous les territoires")

        h.addLayout(col_pole)
        h.addLayout(col_pulled)
        h.addLayout(col_terr)
        return box

    def _build_results_widget(self):
        widget = QWidget()
        v = QVBoxLayout(widget)

        bar = QHBoxLayout()
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText(
            "Filtrer le tableau (ID, commune, motif…)")
        self.txt_filter.textChanged.connect(self._apply_table_filter)
        bar.addWidget(self.txt_filter, 1)

        btn_zoom = QPushButton("Zoomer sur le poteau")
        btn_zoom.setToolTip("Zoome sur le poteau sélectionné (ou double-clic)")
        btn_zoom.clicked.connect(self.on_zoom)
        bar.addWidget(btn_zoom)

        btn_shp = QPushButton("Exporter poteaux (SHP)")
        btn_shp.setToolTip("Exporte les poteaux sortis en shapefile")
        btn_shp.clicked.connect(self.on_export_shapefile)
        bar.addWidget(btn_shp)

        btn_xlsx = QPushButton("Exporter (XLSX)")
        btn_xlsx.clicked.connect(self.on_export)
        bar.addWidget(btn_xlsx)

        v.addLayout(bar)

        self.table = QTableWidget()
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setColumnCount(len(POLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(
            [label for _, label in POLE_COLUMNS])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(lambda *_: self.on_zoom())
        v.addWidget(self.table)
        return widget

    def _build_tab_recap(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)

        outer.addWidget(QLabel(
            "Synthèses calculées sur les poteaux sortis par l'analyse."))

        self.table_recap = QTableWidget()
        self.table_recap.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_recap.setColumnCount(3)
        self.table_recap.setHorizontalHeaderLabels(
            ["Synthèse", "Valeur", "Nombre"])
        self.table_recap.horizontalHeader().setStretchLastSection(True)
        outer.addWidget(self.table_recap)

        row = QHBoxLayout()
        btn_export = QPushButton("Exporter XLSX")
        btn_export.clicked.connect(self.on_export)
        btn_shp = QPushButton("Exporter poteaux (SHP)")
        btn_shp.clicked.connect(self.on_export_shapefile)
        row.addWidget(btn_export)
        row.addWidget(btn_shp)
        row.addStretch()
        outer.addLayout(row)
        return tab

    # ------------------------------------------------------------- Couches
    def _reload_layers(self):
        self._layers = adapter.list_vector_layers()
        self._fill_layer_combo(self.cmb_pole_layer, "poteaux")
        self._fill_layer_combo(self.cmb_cable_layer, "cables")
        self._on_pole_layer()
        self._on_cable_layer()

    def _fill_layer_combo(self, combo, role):
        combo.blockSignals(True)
        combo.clear()
        names = [layer.name() for layer in self._layers]
        for name in names:
            combo.addItem(name)
        guessed = layer_mapping.guess_layer(names, role)
        if guessed and guessed in names:
            combo.setCurrentIndex(names.index(guessed))
        combo.blockSignals(False)

    def _current_layer(self, combo):
        idx = combo.currentIndex()
        if idx < 0 or idx >= len(self._layers):
            return None
        return self._layers[idx]

    def _pole_layer(self):
        return self._current_layer(self.cmb_pole_layer)

    def _cable_layer(self):
        return self._current_layer(self.cmb_cable_layer)

    def _fill_field_combo(self, combo, fields, role, optional=False):
        combo.blockSignals(True)
        combo.clear()
        if optional:
            combo.addItem("(aucun)", "")
        for name in fields:
            combo.addItem(name, name)
        guessed = layer_mapping.guess_field(fields, role)
        if guessed:
            index = combo.findData(guessed)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _on_pole_layer(self, *args):
        fields = adapter.field_names(self._pole_layer())
        self._fill_field_combo(self.cmb_id_poteau, fields, "id_poteau")
        self._fill_field_combo(self.cmb_etat_poteau, fields, "etat_poteau")
        self._fill_field_combo(self.cmb_travaux, fields, "travaux", True)
        self._fill_field_combo(self.cmb_commune, fields, "commune", True)
        self._fill_field_combo(self.cmb_departement, fields, "departement",
                               True)
        self._fill_field_combo(self.cmb_territoire, fields, "territoire", True)

    def _on_cable_layer(self, *args):
        fields = adapter.field_names(self._cable_layer())
        self._fill_field_combo(self.cmb_ref_cable, fields, "ref_cable", True)
        self._fill_field_combo(self.cmb_statut_cable, fields, "statut_cable")

    # ----------------------------------------------- Multi-sélections états
    def _populate_check_list(self, widget, values, default_checked):
        default_norm = {normalize_status(v) for v in default_checked}
        widget.clear()
        for value in values:
            item = QListWidgetItem(value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = normalize_status(value) in default_norm
            item.setCheckState(
                Qt.CheckState.Checked if checked
                else Qt.CheckState.Unchecked)
            widget.addItem(item)

    def _checked_values(self, widget):
        values = []
        for i in range(widget.count()):
            item = widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                values.append(item.text())
        return values

    # ---------------------------------------------------------- Validation
    def _validate_mapping(self):
        errors = []
        if self._pole_layer() is None:
            errors.append("Sélectionnez une couche poteaux.")
        if self._cable_layer() is None:
            errors.append("Sélectionnez une couche câbles.")
        if not self.cmb_id_poteau.currentData():
            errors.append("Champ « ID poteau » obligatoire.")
        if not self.cmb_etat_poteau.currentData():
            errors.append("Champ « État poteau » obligatoire.")
        if not self.cmb_statut_cable.currentData():
            errors.append("Champ « Statut câble » obligatoire.")
        return errors

    def _optional_pole_fields(self):
        return {
            "commune": self.cmb_commune.currentData() or "",
            "departement": self.cmb_departement.currentData() or "",
            "territoire": self.cmb_territoire.currentData() or "",
            "travaux": self.cmb_travaux.currentData() or "",
        }

    def _optional_cable_fields(self):
        # Côté câble on peut réutiliser les mêmes rôles si les champs existent.
        fields = adapter.field_names(self._cable_layer())
        return {
            "commune": layer_mapping.guess_field(fields, "commune") or "",
            "departement": layer_mapping.guess_field(fields, "departement")
            or "",
            "territoire": layer_mapping.guess_field(fields, "territoire") or "",
        }

    # -------------------------------------------------------------- Actions
    def on_test(self):
        errors = self._validate_mapping()
        if errors:
            QMessageBox.warning(self, "Champs manquants", "\n".join(errors))
            return

        pole_layer = self._pole_layer()
        cable_layer = self._cable_layer()
        if not adapter.is_point_layer(pole_layer):
            QMessageBox.warning(
                self, "Couche poteaux",
                "La couche poteaux ne semble pas ponctuelle. "
                "Le rattachement spatial attend des points.")
        if not adapter.is_line_layer(cable_layer):
            QMessageBox.warning(
                self, "Couche câbles",
                "La couche câbles ne semble pas linéaire. "
                "Le rattachement spatial attend des lignes.")

        etat_poteau = self.cmb_etat_poteau.currentData()
        statut_cable = self.cmb_statut_cable.currentData()
        territoire = self.cmb_territoire.currentData()
        pole_states = adapter.distinct_values(pole_layer, etat_poteau)
        cable_states = adapter.distinct_values(cable_layer, statut_cable)
        territoires = (adapter.distinct_values(pole_layer, territoire)
                       if territoire else [])

        self._populate_check_list(
            self.list_pole_states, pole_states, DEFAULT_POLE_STATES)
        self._populate_check_list(
            self.list_pulled, cable_states, DEFAULT_PULLED_STATUSES)
        self._populate_check_list(self.list_territoires, territoires, [])

        n_poles = pole_layer.featureCount()
        n_cables = cable_layer.featureCount()
        QMessageBox.information(
            self, "Test des couches",
            "Couches et champs valides.\n\n"
            "Poteaux détectés : {}\n"
            "Câbles détectés : {}\n"
            "États poteau distincts : {}\n"
            "Statuts câble distincts : {}\n"
            "Territoires distincts : {}".format(
                n_poles, n_cables, len(pole_states), len(cable_states),
                len(territoires)))
        self._save_settings()

    def on_analyse(self):
        errors = self._validate_mapping()
        if errors:
            QMessageBox.warning(self, "Champs manquants", "\n".join(errors))
            return

        if self.list_pulled.count() == 0:
            QMessageBox.warning(
                self, "Tester d'abord",
                "Cliquez sur « Tester les couches / champs » pour charger les "
                "statuts détectés avant d'analyser.")
            return

        pole_layer = self._pole_layer()
        cable_layer = self._cable_layer()

        try:
            self.poles = adapter.extract_poles(
                pole_layer,
                self.cmb_id_poteau.currentData(),
                self.cmb_etat_poteau.currentData(),
                self._optional_pole_fields())
            self.cables = adapter.extract_cables(
                cable_layer,
                self.cmb_statut_cable.currentData(),
                self.cmb_ref_cable.currentData() or None,
                self._optional_cable_fields())
        except Exception as exc:  # noqa: BLE001 - message lisible utilisateur
            QMessageBox.critical(
                self, "Erreur d'extraction",
                "Impossible de lire les couches :\n{}".format(exc))
            return

        pole_states = self._checked_values(self.list_pole_states)
        pulled = self._checked_values(self.list_pulled)
        territoires = self._checked_values(self.list_territoires)
        if not pole_states:
            pole_states = None  # aucun filtre => tous les poteaux

        self.rows, self.counters, self.cable_detail = analyze(
            self.poles, self.cables, pulled,
            buffer_m=self.spin_buffer.value(),
            selected_pole_states=pole_states,
            selected_territoires=territoires or None)

        self._analysis_pole_layer = pole_layer
        self.txt_filter.blockSignals(True)
        self.txt_filter.clear()
        self.txt_filter.blockSignals(False)

        self._fill_result_table(self.rows)
        self._fill_recap_table()
        self._update_counters()
        self._save_settings()

    def on_zoom(self):
        if self.iface is None:
            return
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        if item is None:
            QMessageBox.information(
                self, "Zoom",
                "Sélectionnez d'abord un poteau dans le tableau.")
            return
        fid = item.data(Qt.ItemDataRole.UserRole)
        layer = self._analysis_pole_layer
        if layer is None or fid is None:
            QMessageBox.warning(
                self, "Zoom",
                "Impossible de localiser ce poteau (relancez l'analyse).")
            return
        layer.removeSelection()
        layer.selectByIds([fid])
        canvas = self.iface.mapCanvas()
        canvas.zoomToSelected(layer)
        if canvas.scale() < 1000:
            canvas.zoomScale(1000)
        try:
            canvas.flashFeatureIds(layer, [fid])
        except Exception:  # noqa: BLE001 - flash purement cosmétique
            pass
        canvas.refresh()

    def on_export_shapefile(self):
        if not self.rows:
            QMessageBox.warning(
                self, "Rien à exporter",
                "Lancez d'abord une analyse produisant des poteaux.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter les poteaux (shapefile)",
            "poteaux_sans_cable_tire.shp", "Shapefile (*.shp)")
        if not path:
            return
        if not path.lower().endswith(".shp"):
            path += ".shp"
        try:
            n = adapter.export_poles_shapefile(
                path, self.rows, adapter.TARGET_CRS_AUTHID)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Erreur export",
                "Export shapefile impossible :\n{}".format(exc))
            return
        if self.iface is not None:
            name = os.path.splitext(os.path.basename(path))[0]
            self.iface.addVectorLayer(path, name, "ogr")
        QMessageBox.information(
            self, "Export terminé",
            "{} poteaux exportés :\n{}".format(n, os.path.abspath(path)))

    def on_export(self):
        if not self.rows and not self.counters:
            QMessageBox.warning(
                self, "Rien à exporter",
                "Lancez d'abord une analyse.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter le résultat", "poteaux_sans_cable_tire.xlsx",
            "Classeur Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        context = {
            "couche_poteaux": self.cmb_pole_layer.currentText(),
            "couche_cables": self.cmb_cable_layer.currentText(),
            "champ_id_poteau": self.cmb_id_poteau.currentData(),
            "champ_etat_poteau": self.cmb_etat_poteau.currentData(),
            "champ_statut_cable": self.cmb_statut_cable.currentData(),
            "champ_ref_cable": self.cmb_ref_cable.currentData() or "(aucun)",
            "etats_poteau_retenus":
                self._checked_values(self.list_pole_states) or ["(tous)"],
            "territoires_retenus":
                self._checked_values(self.list_territoires) or ["(tous)"],
            "statuts_tires": self._checked_values(self.list_pulled),
            "buffer_m": self.spin_buffer.value(),
            "crs_analyse": adapter.TARGET_CRS_AUTHID,
            "poteaux_total": self.counters.get("poles_total", 0),
            "poteaux_selectionnes": self.counters.get("poles_selected", 0),
            "cables_total": self.counters.get("cables_total", 0),
            "poteaux_sans_cable_tire":
                self.counters.get("poles_without_pulled", 0),
        }
        params = export_xlsx.build_params(context)
        try:
            export_xlsx.export_xlsx(
                path, self.rows, self.cable_detail, params)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Erreur export", "Export impossible :\n{}".format(exc))
            return
        QMessageBox.information(
            self, "Export terminé",
            "Fichier généré :\n{}".format(os.path.abspath(path)))

    # ------------------------------------------------------------- Affichage
    def _fill_result_table(self, rows):
        self._visible_rows = rows
        keys = [key for key, _ in POLE_COLUMNS]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(keys):
                item = QTableWidgetItem(str(row.get(key, "")))
                if c == 0:
                    # On attache le fid à la 1re cellule : le zoom reste fiable
                    # même après un tri de colonnes par l'utilisateur.
                    item.setData(Qt.ItemDataRole.UserRole, row.get("_fid"))
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    def _apply_table_filter(self, text):
        text = (text or "").strip().lower()
        if not text:
            self._fill_result_table(self.rows)
            return
        keys = [key for key, _ in POLE_COLUMNS]
        filtered = [
            row for row in self.rows
            if any(text in str(row.get(key, "")).lower() for key in keys)
        ]
        self._fill_result_table(filtered)

    def _fill_recap_table(self):
        syntheses = build_syntheses(self.rows, self.cable_detail)
        flat = []
        for title, pairs in syntheses.items():
            if not pairs:
                flat.append((title, "(aucun)", 0))
            for label, nb in pairs:
                flat.append((title, label, nb))
        self.table_recap.setRowCount(len(flat))
        for r, (title, label, nb) in enumerate(flat):
            self.table_recap.setItem(r, 0, QTableWidgetItem(title))
            self.table_recap.setItem(r, 1, QTableWidgetItem(str(label)))
            self.table_recap.setItem(r, 2, QTableWidgetItem(str(nb)))
        self.table_recap.resizeColumnsToContents()

    def _update_counters(self):
        c = self.counters
        self.lbl_counters.setText(
            "Poteaux analysés : {poles_total}   |   "
            "Poteaux remplacés / implantés : {poles_selected}   |   "
            "Câbles analysés : {cables_total}   |   "
            "Poteaux sans câble tiré : {poles_without_pulled}   |   "
            "Statuts câble distincts : {cable_status_distinct}".format(**c))

    # -------------------------------------------------------------- QSettings
    def _save_settings(self):
        s = self.settings
        s.setValue(SETTINGS_PREFIX + "pole_layer",
                   self.cmb_pole_layer.currentText())
        s.setValue(SETTINGS_PREFIX + "cable_layer",
                   self.cmb_cable_layer.currentText())
        s.setValue(SETTINGS_PREFIX + "id_poteau",
                   self.cmb_id_poteau.currentData())
        s.setValue(SETTINGS_PREFIX + "etat_poteau",
                   self.cmb_etat_poteau.currentData())
        s.setValue(SETTINGS_PREFIX + "travaux",
                   self.cmb_travaux.currentData())
        s.setValue(SETTINGS_PREFIX + "ref_cable",
                   self.cmb_ref_cable.currentData())
        s.setValue(SETTINGS_PREFIX + "statut_cable",
                   self.cmb_statut_cable.currentData())
        s.setValue(SETTINGS_PREFIX + "commune",
                   self.cmb_commune.currentData())
        s.setValue(SETTINGS_PREFIX + "departement",
                   self.cmb_departement.currentData())
        s.setValue(SETTINGS_PREFIX + "territoire",
                   self.cmb_territoire.currentData())
        s.setValue(SETTINGS_PREFIX + "buffer", self.spin_buffer.value())

    def _restore_combo(self, combo, key, by_data=True):
        value = self.settings.value(SETTINGS_PREFIX + key, None)
        if value in (None, ""):
            return
        index = combo.findData(value) if by_data else combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _load_settings(self):
        self._restore_combo(self.cmb_pole_layer, "pole_layer", by_data=False)
        self._restore_combo(self.cmb_cable_layer, "cable_layer", by_data=False)
        self._on_pole_layer()
        self._on_cable_layer()
        self._restore_combo(self.cmb_id_poteau, "id_poteau")
        self._restore_combo(self.cmb_etat_poteau, "etat_poteau")
        self._restore_combo(self.cmb_travaux, "travaux")
        self._restore_combo(self.cmb_ref_cable, "ref_cable")
        self._restore_combo(self.cmb_statut_cable, "statut_cable")
        self._restore_combo(self.cmb_commune, "commune")
        self._restore_combo(self.cmb_departement, "departement")
        self._restore_combo(self.cmb_territoire, "territoire")
        buffer_value = self.settings.value(SETTINGS_PREFIX + "buffer", None)
        if buffer_value not in (None, ""):
            try:
                self.spin_buffer.setValue(float(buffer_value))
            except (TypeError, ValueError):
                pass
