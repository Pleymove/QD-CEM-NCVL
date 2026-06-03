"""Fenêtre principale du plugin CEM NCVL — interface à onglets.

Onglet 1 « Analyse poteaux » : sélection des couches, mapping des champs,
test, multi-sélection des états (poteau / câble tiré), buffer, analyse et
tableau résultat.

Onglet 2 « Récap TCD / export » : synthèses calculées et export XLSX.

L'interface ne porte aucune logique métier : elle prépare les données via
``qgis_adapter`` puis délègue à ``core`` (analyse, synthèses, export).
"""

import os

from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)

from .. import qgis_adapter as adapter
from ..core import layer_mapping
from ..core.cable_filters import DEFAULT_PULLED_STATUSES
from ..core.columns import POLE_COLUMNS
from ..core.poteaux_analysis import analyze, DEFAULT_BUFFER_M, DEFAULT_POLE_STATES
from ..core.synthese import build_syntheses, build_tcd_table
from ..core import export_xlsx
from ..core.normalize import normalize_status

SETTINGS_PREFIX = "cem_ncvl_plugin/"

# Champs optionnels mappés côté poteaux.
OPTIONAL_ROLES = ["commune", "departement", "territoire"]


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

        self.setWindowTitle("CEM NCVL — Poteaux sans câble tiré")
        self.resize(1000, 720)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_tab_analyse(), "Analyse poteaux")
        self.tabs.addTab(self._build_tab_recap(), "Récap TCD / export")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self._reload_layers()
        self._load_settings()

    # ------------------------------------------------------------------ UI
    def _build_tab_analyse(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)

        # --- Couches & champs ---
        box_layers = QGroupBox("Couches et champs")
        form = QFormLayout(box_layers)

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
        self.cmb_ref_cable = QComboBox()
        self.cmb_statut_cable = QComboBox()
        self.cmb_commune = QComboBox()
        self.cmb_departement = QComboBox()
        self.cmb_territoire = QComboBox()

        form.addRow("ID poteau *", self.cmb_id_poteau)
        form.addRow("État poteau *", self.cmb_etat_poteau)
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
        form.addRow("Rayon de recherche autour du poteau", self.spin_buffer)

        btn_test = QPushButton("Tester les couches / champs")
        btn_test.clicked.connect(self.on_test)
        form.addRow(btn_test)

        outer.addWidget(box_layers)

        # --- Filtres états ---
        box_filters = QGroupBox("Filtres métier")
        h = QHBoxLayout(box_filters)

        col_pole = QVBoxLayout()
        col_pole.addWidget(QLabel("États poteau à analyser\n"
                                  "(cas client : famille « plante »)"))
        self.list_pole_states = QListWidget()
        self.list_pole_states.setSelectionMode(
            QAbstractItemView.NoSelection)
        col_pole.addWidget(self.list_pole_states)
        h.addLayout(col_pole)

        col_cable = QVBoxLayout()
        col_cable.addWidget(QLabel("Statuts câble considérés comme « tirés »"))
        self.list_pulled = QListWidget()
        self.list_pulled.setSelectionMode(QAbstractItemView.NoSelection)
        col_cable.addWidget(self.list_pulled)
        h.addLayout(col_cable)

        outer.addWidget(box_filters)

        # --- Action analyse + compteurs ---
        btn_analyse = QPushButton("Analyser")
        btn_analyse.clicked.connect(self.on_analyse)
        outer.addWidget(btn_analyse)

        self.lbl_counters = QLabel("Aucune analyse lancée.")
        self.lbl_counters.setWordWrap(True)
        outer.addWidget(self.lbl_counters)

        # --- Tableau résultat ---
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnCount(len(POLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(
            [label for _, label in POLE_COLUMNS])
        outer.addWidget(self.table)

        return tab

    def _build_tab_recap(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)

        outer.addWidget(QLabel(
            "Synthèses calculées sur les poteaux sortis par l'analyse."))

        self.table_recap = QTableWidget()
        self.table_recap.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_recap.setColumnCount(3)
        self.table_recap.setHorizontalHeaderLabels(
            ["Synthèse", "Valeur", "Nombre"])
        outer.addWidget(self.table_recap)

        btn_export = QPushButton("Exporter XLSX")
        btn_export.clicked.connect(self.on_export)
        outer.addWidget(btn_export)

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
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            checked = normalize_status(value) in default_norm
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            widget.addItem(item)

    def _checked_values(self, widget):
        values = []
        for i in range(widget.count()):
            item = widget.item(i)
            if item.checkState() == Qt.Checked:
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
        pole_states = adapter.distinct_values(pole_layer, etat_poteau)
        cable_states = adapter.distinct_values(cable_layer, statut_cable)

        self._populate_check_list(
            self.list_pole_states, pole_states, DEFAULT_POLE_STATES)
        self._populate_check_list(
            self.list_pulled, cable_states, DEFAULT_PULLED_STATUSES)

        n_poles = pole_layer.featureCount()
        n_cables = cable_layer.featureCount()
        QMessageBox.information(
            self, "Test des couches",
            "Couches et champs valides.\n\n"
            "Poteaux détectés : {}\n"
            "Câbles détectés : {}\n"
            "États poteau distincts : {}\n"
            "Statuts câble distincts : {}".format(
                n_poles, n_cables, len(pole_states), len(cable_states)))
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
        if not pole_states:
            pole_states = None  # aucun filtre => tous les poteaux

        self.rows, self.counters, self.cable_detail = analyze(
            self.poles, self.cables, pulled,
            buffer_m=self.spin_buffer.value(),
            selected_pole_states=pole_states)

        self._fill_result_table()
        self._fill_recap_table()
        self._update_counters()
        self._save_settings()

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
    def _fill_result_table(self):
        keys = [key for key, _ in POLE_COLUMNS]
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            for c, key in enumerate(keys):
                self.table.setItem(
                    r, c, QTableWidgetItem(str(row.get(key, ""))))
        self.table.resizeColumnsToContents()

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
