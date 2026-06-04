"""Onglet « Analyse GC souterrain » du plugin CEM NCVL.

Sélection des couches GC / câble, mapping des champs GC, filtres (états
travaux GC / statuts câble tirés / territoire), rattachement spatial
ligne↔ligne en EPSG:2154, tableau résultat avec zoom carte et exports
XLSX / shapefile.

Module d'interface uniquement : délègue l'extraction à ``qgis_adapter`` et la
logique à ``core.gc_analysis`` / ``core.export_xlsx`` (testés hors QGIS).
"""

import os

from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QScrollArea, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import qgis_adapter as adapter
from ..core import layer_mapping
from ..core import export_xlsx
from ..core.cable_filters import DEFAULT_PULLED_STATUSES
from ..core.columns import GC_COLUMNS
from ..core.gc_analysis import (
    analyze_gc, DEFAULT_GC_BUFFER_M, DEFAULT_GC_DONE_STATES,
)
from ..core.normalize import normalize_status

SETTINGS_PREFIX = "cem_ncvl_plugin/gc_"


class GcAnalysisTab(QWidget):
    """Widget de l'onglet d'analyse des GC souterrains."""

    def __init__(self, iface=None, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.settings = QSettings()

        self.rows = []
        self.counters = {}
        self.cable_detail = []
        self._analysis_gc_layer = None
        self._layers = []

        self._build_ui()
        self._reload_layers()
        self._load_settings()

    # ------------------------------------------------------------ UI helpers
    def _build_checklist_column(self, title, tooltip=""):
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

    def _build_ui(self):
        outer = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(splitter)

        config = QWidget()
        cfg = QVBoxLayout(config)
        cfg.addWidget(self._build_box_layers())
        cfg.addWidget(self._build_box_filters())

        btn_analyse = QPushButton("Analyser les GC")
        btn_analyse.setMinimumHeight(34)
        btn_analyse.setStyleSheet("font-weight: bold;")
        btn_analyse.clicked.connect(self.on_analyse)
        cfg.addWidget(btn_analyse)

        self.lbl_counters = QLabel("Aucune analyse GC lancée.")
        self.lbl_counters.setWordWrap(True)
        self.lbl_counters.setStyleSheet("font-weight: bold; color: #1F4E78;")
        cfg.addWidget(self.lbl_counters)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(config)
        splitter.addWidget(scroll)

        splitter.addWidget(self._build_results_widget())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 360])

    def _build_box_layers(self):
        box = QGroupBox("1. Couches et champs GC")
        form = QFormLayout(box)

        self.cmb_gc_layer = QComboBox()
        self.cmb_cable_layer = QComboBox()
        self.cmb_gc_layer.currentIndexChanged.connect(self._on_gc_layer)
        self.cmb_cable_layer.currentIndexChanged.connect(self._on_cable_layer)

        btn_reload = QPushButton("Recharger les couches")
        btn_reload.clicked.connect(self._reload_layers)
        row_gc = QHBoxLayout()
        row_gc.addWidget(self.cmb_gc_layer)
        row_gc.addWidget(btn_reload)
        wrap_gc = QWidget()
        wrap_gc.setLayout(row_gc)

        form.addRow("Couche GC *", wrap_gc)
        form.addRow("Couche câbles *", self.cmb_cable_layer)

        self.cmb_id_gc = QComboBox()
        self.cmb_nom_gc = QComboBox()
        self.cmb_suivi = QComboBox()
        self.cmb_statut_cable = QComboBox()
        self.cmb_ref_cable = QComboBox()
        self.cmb_commune = QComboBox()
        self.cmb_departement = QComboBox()
        self.cmb_plaque = QComboBox()
        self.cmb_longueur = QComboBox()

        self.cmb_id_gc.setToolTip("Identifiant technique du GC (ex. id_0)")
        self.cmb_nom_gc.setToolTip(
            "Libellé / code GC affiché (ex. nom). Si vide, l'ID est utilisé.")
        self.cmb_suivi.setToolTip("Champ de suivi des travaux GC (suivi_pilotage)")
        self.cmb_plaque.setToolTip("Plaque / territoire (filtre et synthèses)")

        form.addRow("ID GC *", self.cmb_id_gc)
        form.addRow("Nom / code GC", self.cmb_nom_gc)
        form.addRow("Suivi travaux GC *", self.cmb_suivi)
        form.addRow("Statut câble *", self.cmb_statut_cable)
        form.addRow("Référence câble", self.cmb_ref_cable)
        form.addRow("Commune", self.cmb_commune)
        form.addRow("Département", self.cmb_departement)
        form.addRow("Plaque / territoire", self.cmb_plaque)
        form.addRow("Longueur (ml)", self.cmb_longueur)

        self.spin_buffer = QDoubleSpinBox()
        self.spin_buffer.setRange(0.0, 1000.0)
        self.spin_buffer.setDecimals(1)
        self.spin_buffer.setSingleStep(0.5)
        self.spin_buffer.setValue(DEFAULT_GC_BUFFER_M)
        self.spin_buffer.setSuffix(" m")
        self.spin_buffer.setToolTip(
            "Tolérance de rattachement câble↔GC (0 = intersection stricte). "
            "Analyse en EPSG:2154.")
        form.addRow("Tolérance de rattachement", self.spin_buffer)

        btn_test = QPushButton("Tester les couches / champs")
        btn_test.clicked.connect(self.on_test)
        form.addRow(btn_test)
        return box

    def _build_box_filters(self):
        box = QGroupBox("2. Filtres métier (cliquer « Tester » pour les remplir)")
        h = QHBoxLayout(box)
        col_done, self.list_done = self._build_checklist_column(
            "États GC « travaux faits »",
            "Par défaut : TRX fini + facturation (modifiable)")
        col_pulled, self.list_pulled = self._build_checklist_column(
            "Statuts câble « tirés »",
            "Un GC sort si aucun câble rattaché n'a un de ces statuts")
        col_terr, self.list_territoires = self._build_checklist_column(
            "Territoire / plaque",
            "Laisser vide = analyser tous les territoires")
        h.addLayout(col_done)
        h.addLayout(col_pulled)
        h.addLayout(col_terr)
        return box

    def _build_results_widget(self):
        widget = QWidget()
        v = QVBoxLayout(widget)

        bar = QHBoxLayout()
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText(
            "Filtrer le tableau (ID, nom, commune, motif…)")
        self.txt_filter.textChanged.connect(self._apply_table_filter)
        bar.addWidget(self.txt_filter, 1)

        btn_zoom = QPushButton("Zoomer sur le GC")
        btn_zoom.clicked.connect(self.on_zoom)
        bar.addWidget(btn_zoom)
        btn_shp = QPushButton("Exporter GC (SHP)")
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
        self.table.setColumnCount(len(GC_COLUMNS))
        self.table.setHorizontalHeaderLabels(
            [label for _, label in GC_COLUMNS])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(lambda *_: self.on_zoom())
        v.addWidget(self.table)
        return widget

    # ------------------------------------------------------------- Couches
    def _reload_layers(self):
        self._layers = adapter.list_vector_layers()
        self._fill_layer_combo(self.cmb_gc_layer, "gc")
        self._fill_layer_combo(self.cmb_cable_layer, "cables")
        self._on_gc_layer()
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

    def _gc_layer(self):
        return self._current_layer(self.cmb_gc_layer)

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

    def _on_gc_layer(self, *args):
        fields = adapter.field_names(self._gc_layer())
        self._fill_field_combo(self.cmb_id_gc, fields, "id_gc")
        self._fill_field_combo(self.cmb_nom_gc, fields, "nom_gc", True)
        self._fill_field_combo(self.cmb_suivi, fields, "suivi_pilotage")
        self._fill_field_combo(self.cmb_commune, fields, "commune", True)
        self._fill_field_combo(self.cmb_departement, fields, "departement",
                               True)
        self._fill_field_combo(self.cmb_plaque, fields, "plaque", True)
        self._fill_field_combo(self.cmb_longueur, fields, "longueur", True)

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
        if self._gc_layer() is None:
            errors.append("Sélectionnez une couche GC.")
        if self._cable_layer() is None:
            errors.append("Sélectionnez une couche câbles.")
        if not self.cmb_id_gc.currentData():
            errors.append("Champ « ID GC » obligatoire.")
        if not self.cmb_suivi.currentData():
            errors.append("Champ « Suivi travaux GC » obligatoire.")
        if not self.cmb_statut_cable.currentData():
            errors.append("Champ « Statut câble » obligatoire.")
        return errors

    def _gc_optional_fields(self):
        return {
            "commune": self.cmb_commune.currentData() or "",
            "departement": self.cmb_departement.currentData() or "",
            "territoire": self.cmb_plaque.currentData() or "",
            "longueur": self.cmb_longueur.currentData() or "",
        }

    def _cable_optional_fields(self):
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

        gc_layer = self._gc_layer()
        cable_layer = self._cable_layer()
        if not adapter.is_line_layer(gc_layer):
            QMessageBox.warning(
                self, "Couche GC",
                "La couche GC ne semble pas linéaire. Le rattachement "
                "spatial attend des lignes.")
        if not adapter.is_line_layer(cable_layer):
            QMessageBox.warning(
                self, "Couche câbles",
                "La couche câbles ne semble pas linéaire.")

        suivi = self.cmb_suivi.currentData()
        statut_cable = self.cmb_statut_cable.currentData()
        plaque = self.cmb_plaque.currentData()
        done_states = adapter.distinct_values(gc_layer, suivi)
        cable_states = adapter.distinct_values(cable_layer, statut_cable)
        territoires = (adapter.distinct_values(gc_layer, plaque)
                       if plaque else [])

        self._populate_check_list(
            self.list_done, done_states, DEFAULT_GC_DONE_STATES)
        self._populate_check_list(
            self.list_pulled, cable_states, DEFAULT_PULLED_STATUSES)
        self._populate_check_list(self.list_territoires, territoires, [])

        QMessageBox.information(
            self, "Test des couches",
            "Couches et champs valides.\n\n"
            "GC détectés : {}\n"
            "Câbles détectés : {}\n"
            "États suivi GC distincts : {}\n"
            "Statuts câble distincts : {}\n"
            "Territoires distincts : {}".format(
                gc_layer.featureCount(), cable_layer.featureCount(),
                len(done_states), len(cable_states), len(territoires)))
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

        gc_layer = self._gc_layer()
        cable_layer = self._cable_layer()
        try:
            gcs = adapter.extract_gc(
                gc_layer,
                self.cmb_id_gc.currentData(),
                self.cmb_suivi.currentData(),
                label_field=self.cmb_nom_gc.currentData() or None,
                optional_fields=self._gc_optional_fields())
            cables = adapter.extract_cables(
                cable_layer,
                self.cmb_statut_cable.currentData(),
                self.cmb_ref_cable.currentData() or None,
                self._cable_optional_fields())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Erreur d'extraction",
                "Impossible de lire les couches :\n{}".format(exc))
            return

        done_states = self._checked_values(self.list_done)
        pulled = self._checked_values(self.list_pulled)
        territoires = self._checked_values(self.list_territoires)

        self.rows, self.counters, self.cable_detail = analyze_gc(
            gcs, cables, pulled,
            buffer_m=self.spin_buffer.value(),
            selected_done_states=done_states or None,
            selected_territoires=territoires or None)

        self._analysis_gc_layer = gc_layer
        self.txt_filter.blockSignals(True)
        self.txt_filter.clear()
        self.txt_filter.blockSignals(False)
        self._fill_result_table(self.rows)
        self._update_counters()
        self._save_settings()

    def on_zoom(self):
        if self.iface is None:
            return
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        if item is None:
            QMessageBox.information(
                self, "Zoom", "Sélectionnez d'abord un GC dans le tableau.")
            return
        fid = item.data(Qt.ItemDataRole.UserRole)
        layer = self._analysis_gc_layer
        if layer is None or fid is None:
            QMessageBox.warning(
                self, "Zoom",
                "Impossible de localiser ce GC (relancez l'analyse).")
            return
        layer.removeSelection()
        layer.selectByIds([fid])
        canvas = self.iface.mapCanvas()
        canvas.zoomToSelected(layer)
        if canvas.scale() < 1000:
            canvas.zoomScale(1000)
        try:
            canvas.flashFeatureIds(layer, [fid])
        except Exception:  # noqa: BLE001
            pass
        canvas.refresh()

    def on_export_shapefile(self):
        if not self.rows:
            QMessageBox.warning(
                self, "Rien à exporter",
                "Lancez d'abord une analyse produisant des GC.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter les GC (shapefile)",
            "gc_sans_cable_tire.shp", "Shapefile (*.shp)")
        if not path:
            return
        if not path.lower().endswith(".shp"):
            path += ".shp"
        try:
            n = adapter.export_gc_shapefile(
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
            "{} GC exportés :\n{}".format(n, os.path.abspath(path)))

    def on_export(self):
        if not self.rows and not self.counters:
            QMessageBox.warning(
                self, "Rien à exporter", "Lancez d'abord une analyse GC.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter le résultat GC", "gc_sans_cable_tire.xlsx",
            "Classeur Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        context = {
            "couche_gc": self.cmb_gc_layer.currentText(),
            "couche_cables": self.cmb_cable_layer.currentText(),
            "champ_id_gc": self.cmb_id_gc.currentData(),
            "champ_nom_gc": self.cmb_nom_gc.currentData() or "(aucun)",
            "champ_suivi": self.cmb_suivi.currentData(),
            "etats_gc_retenus":
                self._checked_values(self.list_done) or ["(tous)"],
            "territoires_retenus":
                self._checked_values(self.list_territoires) or ["(tous)"],
            "statuts_tires": self._checked_values(self.list_pulled),
            "buffer_m": self.spin_buffer.value(),
            "crs_analyse": adapter.TARGET_CRS_AUTHID,
            "gc_total": self.counters.get("gc_total", 0),
            "gc_selectionnes": self.counters.get("gc_selected", 0),
            "cables_total": self.counters.get("cables_total", 0),
            "gc_sans_cable_tire": self.counters.get("gc_without_pulled", 0),
        }
        params = export_xlsx.build_gc_params(context)
        try:
            export_xlsx.export_gc_xlsx(
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
        keys = [key for key, _ in GC_COLUMNS]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(keys):
                item = QTableWidgetItem(str(row.get(key, "")))
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row.get("_fid"))
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    def _apply_table_filter(self, text):
        text = (text or "").strip().lower()
        if not text:
            self._fill_result_table(self.rows)
            return
        keys = [key for key, _ in GC_COLUMNS]
        filtered = [
            row for row in self.rows
            if any(text in str(row.get(key, "")).lower() for key in keys)
        ]
        self._fill_result_table(filtered)

    def _update_counters(self):
        c = self.counters
        self.lbl_counters.setText(
            "GC analysés : {gc_total}   |   "
            "GC travaux faits : {gc_selected}   |   "
            "Câbles analysés : {cables_total}   |   "
            "GC sans câble tiré : {gc_without_pulled}   |   "
            "Statuts câble distincts : {cable_status_distinct}".format(**c))

    # -------------------------------------------------------------- QSettings
    def _save_settings(self):
        s = self.settings
        mapping = {
            "gc_layer": self.cmb_gc_layer.currentText(),
            "cable_layer": self.cmb_cable_layer.currentText(),
            "id_gc": self.cmb_id_gc.currentData(),
            "nom_gc": self.cmb_nom_gc.currentData(),
            "suivi": self.cmb_suivi.currentData(),
            "statut_cable": self.cmb_statut_cable.currentData(),
            "ref_cable": self.cmb_ref_cable.currentData(),
            "commune": self.cmb_commune.currentData(),
            "departement": self.cmb_departement.currentData(),
            "plaque": self.cmb_plaque.currentData(),
            "longueur": self.cmb_longueur.currentData(),
        }
        for key, value in mapping.items():
            s.setValue(SETTINGS_PREFIX + key, value)
        s.setValue(SETTINGS_PREFIX + "buffer", self.spin_buffer.value())

    def _restore_combo(self, combo, key, by_data=True):
        value = self.settings.value(SETTINGS_PREFIX + key, None)
        if value in (None, ""):
            return
        index = combo.findData(value) if by_data else combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _load_settings(self):
        self._restore_combo(self.cmb_gc_layer, "gc_layer", by_data=False)
        self._restore_combo(self.cmb_cable_layer, "cable_layer", by_data=False)
        self._on_gc_layer()
        self._on_cable_layer()
        self._restore_combo(self.cmb_id_gc, "id_gc")
        self._restore_combo(self.cmb_nom_gc, "nom_gc")
        self._restore_combo(self.cmb_suivi, "suivi")
        self._restore_combo(self.cmb_statut_cable, "statut_cable")
        self._restore_combo(self.cmb_ref_cable, "ref_cable")
        self._restore_combo(self.cmb_commune, "commune")
        self._restore_combo(self.cmb_departement, "departement")
        self._restore_combo(self.cmb_plaque, "plaque")
        self._restore_combo(self.cmb_longueur, "longueur")
        buffer_value = self.settings.value(SETTINGS_PREFIX + "buffer", None)
        if buffer_value not in (None, ""):
            try:
                self.spin_buffer.setValue(float(buffer_value))
            except (TypeError, ValueError):
                pass
