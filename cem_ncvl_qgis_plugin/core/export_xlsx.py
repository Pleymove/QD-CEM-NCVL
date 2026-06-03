"""Export XLSX du résultat d'analyse (openpyxl).

Feuilles produites :
- ``Paramètres``      : contexte de l'export (date, couches, champs, filtres) ;
- ``Liste poteaux``   : détail des poteaux sortis (table structurée) ;
- ``Câbles associés`` : détail des câbles rattachés aux poteaux sortis ;
- ``Synthèse``        : tableaux récapitulatifs calculés côté Python ;
- ``TCD``             : table à plat prête à pivoter.

L'export ne dépend pas de QGIS : il peut être généré et testé hors QGIS.
"""

from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from .columns import POLE_COLUMNS, CABLE_COLUMNS
from .synthese import build_syntheses, build_tcd_table, TCD_COLUMNS

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=12, color="1F4E78")


def _style_header(ws, row, ncols):
    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def _autosize(ws, ncols, max_width=60):
    for col in range(1, ncols + 1):
        letter = get_column_letter(col)
        width = 10
        for cell in ws[letter]:
            value = cell.value
            if value is not None:
                width = max(width, min(max_width, len(str(value)) + 2))
        ws.column_dimensions[letter].width = width


def _write_table_sheet(ws, columns, data, table_name):
    """Écrit une feuille avec en-tête figé, auto-filtre et table structurée."""
    labels = [label for _, label in columns]
    keys = [key for key, _ in columns]

    ws.append(labels)
    _style_header(ws, 1, len(labels))

    for row in data:
        ws.append([row.get(key, "") for key in keys])

    nrows = len(data) + 1
    ncols = len(labels)
    last_cell = "{}{}".format(get_column_letter(ncols), nrows)

    # Une table Excel structurée exige au moins une ligne de données.
    if data:
        table = Table(displayName=table_name, ref="A1:{}".format(last_cell))
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2", showRowStripes=True,
        )
        ws.add_table(table)
    else:
        ws.auto_filter.ref = "A1:{}".format(get_column_letter(ncols) + "1")

    ws.freeze_panes = "A2"
    _autosize(ws, ncols)


def _write_params_sheet(ws, params):
    ws["A1"] = "Paramètres de l'analyse CEM NCVL"
    ws["A1"].font = TITLE_FONT
    ws.append([])
    ws.append(["Paramètre", "Valeur"])
    _style_header(ws, 3, 2)
    for label, value in params:
        if isinstance(value, (list, tuple, set)):
            value = " ; ".join(str(v) for v in value)
        ws.append([label, value])
    ws.freeze_panes = "A4"
    _autosize(ws, 2, max_width=80)


def _write_synthese_sheet(ws, syntheses):
    ws["A1"] = "Synthèses"
    ws["A1"].font = TITLE_FONT
    current = 3
    for title, pairs in syntheses.items():
        ws.cell(row=current, column=1, value=title).font = Font(bold=True)
        current += 1
        ws.cell(row=current, column=1, value="Valeur")
        ws.cell(row=current, column=2, value="Nombre")
        _style_header(ws, current, 2)
        current += 1
        for label, nb in pairs:
            ws.cell(row=current, column=1, value=label)
            ws.cell(row=current, column=2, value=nb)
            current += 1
        current += 1  # ligne vide entre deux tableaux
    _autosize(ws, 2, max_width=60)


def _write_tcd_sheet(ws, tcd_rows):
    labels = [label for _, label in TCD_COLUMNS] + ["Nb poteaux"]
    keys = [key for key, _ in TCD_COLUMNS] + ["nb_poteaux"]
    ws.append(labels)
    _style_header(ws, 1, len(labels))
    for row in tcd_rows:
        ws.append([row.get(key, "") for key in keys])
    ncols = len(labels)
    if tcd_rows:
        last = "{}{}".format(get_column_letter(ncols), len(tcd_rows) + 1)
        table = Table(displayName="TCD_Poteaux", ref="A1:{}".format(last))
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium9", showRowStripes=True,
        )
        ws.add_table(table)
    else:
        ws.auto_filter.ref = "A1:{}1".format(get_column_letter(ncols))
    ws.freeze_panes = "A2"
    _autosize(ws, ncols)


def build_workbook(rows, cable_detail, params):
    """Construit et renvoie le ``Workbook`` openpyxl (sans l'enregistrer)."""
    wb = Workbook()

    ws_params = wb.active
    ws_params.title = "Paramètres"
    _write_params_sheet(ws_params, params)

    _write_table_sheet(
        wb.create_sheet("Liste poteaux"), POLE_COLUMNS, rows, "ListePoteaux",
    )
    _write_table_sheet(
        wb.create_sheet("Câbles associés"), CABLE_COLUMNS, cable_detail,
        "CablesAssocies",
    )
    _write_synthese_sheet(
        wb.create_sheet("Synthèse"), build_syntheses(rows, cable_detail),
    )
    _write_tcd_sheet(wb.create_sheet("TCD"), build_tcd_table(rows))
    return wb


def export_xlsx(path, rows, cable_detail, params):
    """Génère le fichier XLSX à ``path`` et renvoie ce chemin."""
    wb = build_workbook(rows, cable_detail, params)
    wb.save(path)
    return path


def build_params(context):
    """Met en forme le contexte d'export en liste (label, valeur) ordonnée.

    ``context`` est un dict libre fourni par l'interface ; les clés connues
    sont ordonnées, les autres ajoutées ensuite.
    """
    context = dict(context or {})
    ordered_labels = [
        ("date_export", "Date d'export"),
        ("couche_poteaux", "Couche poteaux"),
        ("couche_cables", "Couche câbles"),
        ("champ_id_poteau", "Champ ID poteau"),
        ("champ_etat_poteau", "Champ état poteau"),
        ("champ_statut_cable", "Champ statut câble"),
        ("champ_ref_cable", "Champ référence câble"),
        ("etats_poteau_retenus", "États poteau retenus"),
        ("statuts_tires", "Statuts câble « tirés »"),
        ("buffer_m", "Rayon buffer (m)"),
        ("crs_analyse", "CRS d'analyse"),
        ("poteaux_total", "Poteaux analysés"),
        ("poteaux_selectionnes", "Poteaux remplacés / implantés"),
        ("cables_total", "Câbles analysés"),
        ("poteaux_sans_cable_tire", "Poteaux sans câble tiré"),
    ]
    params = []
    if "date_export" not in context:
        context["date_export"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    used = set()
    for key, label in ordered_labels:
        if key in context:
            params.append((label, context[key]))
            used.add(key)
    for key, value in context.items():
        if key not in used:
            params.append((key, value))
    return params
