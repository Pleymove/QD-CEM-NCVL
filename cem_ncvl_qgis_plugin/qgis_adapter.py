"""Pont entre les couches QGIS et la logique métier (``core``).

Ce module :
- liste les couches vecteur ouvertes et leurs champs ;
- extrait les valeurs distinctes d'un champ (alimentation des multi-sélections) ;
- convertit les entités en objets ``Pole`` / ``Cable`` du module ``core``,
  en reprojetant systématiquement les géométries dans un CRS métrique
  (EPSG:2154 par défaut), seul CRS où les distances en mètres ont un sens.

C'est le seul module « métier » qui importe QGIS ; il isole ainsi la
dépendance et garde ``core`` testable hors QGIS.
"""

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsVectorLayer,
)

from .core.models import Pole, Cable, GcArtere

TARGET_CRS_AUTHID = "EPSG:2154"

# Constantes de type de géométrie compatibles QGIS 3 et QGIS 4 (Qt6).
# QGIS 4 expose l'énumération via ``Qgis.GeometryType`` ; QGIS 3 via
# ``QgsWkbTypes`` (formes courtes supprimées sous PyQt6).
try:  # QGIS >= 3.30 / QGIS 4
    from qgis.core import Qgis
    _POINT_GEOM = Qgis.GeometryType.Point
    _LINE_GEOM = Qgis.GeometryType.Line
except (ImportError, AttributeError):  # repli QGIS 3 ancien
    from qgis.core import QgsWkbTypes
    _POINT_GEOM = QgsWkbTypes.PointGeometry
    _LINE_GEOM = QgsWkbTypes.LineGeometry


def list_vector_layers():
    """Renvoie les couches vecteur du projet courant (objets QgsVectorLayer)."""
    layers = []
    for layer in QgsProject.instance().mapLayers().values():
        # isinstance est robuste quelle que soit la version QGIS / l'API enum.
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            layers.append(layer)
    return layers


def field_names(layer):
    """Noms des champs d'une couche."""
    if layer is None:
        return []
    return [field.name() for field in layer.fields()]


def distinct_values(layer, field_name, limit=2000):
    """Valeurs distinctes (libellés source) d'un champ, triées."""
    if layer is None or not field_name:
        return []
    idx = layer.fields().indexOf(field_name)
    if idx < 0:
        return []
    values = set()
    for value in layer.uniqueValues(idx, limit):
        if value is None:
            continue
        text = str(value).strip()
        if text:
            values.add(text)
    return sorted(values)


def _transform_for(layer, target_crs):
    src = layer.crs()
    if not src.isValid() or src == target_crs:
        return None
    return QgsCoordinateTransform(src, target_crs, QgsProject.instance())


def _point_xy(geom, transform):
    if geom is None or geom.isEmpty():
        return None
    # QgsGeometry.transform() mute la géométrie en place et renvoie un code.
    if transform is not None:
        geom.transform(transform)
    point = geom.centroid().asPoint()
    return (point.x(), point.y())


def _lines_xy(geom, transform):
    if geom is None or geom.isEmpty():
        return []
    if transform is not None:
        geom.transform(transform)
    if geom.isMultipart():
        multi = geom.asMultiPolyline()
        return [[(p.x(), p.y()) for p in line] for line in multi]
    line = geom.asPolyline()
    return [[(p.x(), p.y()) for p in line]]


def _attrs(feature, mapping):
    """Construit le dict d'attributs optionnels à partir du mapping fourni.

    ``mapping`` est un dict ``rôle -> nom de champ`` (ex. commune, departement,
    territoire, travaux). Un champ vide donne une valeur vide.
    """
    attrs = {}
    for key, field in mapping.items():
        if field:
            value = feature[field]
            attrs[key] = "" if value is None else str(value)
        else:
            attrs[key] = ""
    return attrs


def extract_poles(layer, id_field, state_field, optional_fields=None,
                  target_authid=TARGET_CRS_AUTHID):
    """Extrait les poteaux d'une couche ponctuelle vers des ``Pole``."""
    optional_fields = optional_fields or {}
    target = QgsCoordinateReferenceSystem(target_authid)
    transform = _transform_for(layer, target)

    poles = []
    for feature in layer.getFeatures():
        xy = _point_xy(feature.geometry(), transform)
        state = feature[state_field]
        poles.append(Pole(
            id=str(feature[id_field]) if feature[id_field] is not None else "",
            state="" if state is None else str(state),
            xy=xy,
            attrs=_attrs(feature, optional_fields),
            fid=feature.id(),
        ))
    return poles


def extract_cables(layer, status_field, ref_field=None, optional_fields=None,
                   target_authid=TARGET_CRS_AUTHID):
    """Extrait les câbles d'une couche linéaire vers des ``Cable``."""
    optional_fields = optional_fields or {}
    target = QgsCoordinateReferenceSystem(target_authid)
    transform = _transform_for(layer, target)

    cables = []
    for feature in layer.getFeatures():
        lines = _lines_xy(feature.geometry(), transform)
        status = feature[status_field]
        ref = feature[ref_field] if ref_field else None
        cables.append(Cable(
            ref="" if ref is None else str(ref),
            status="" if status is None else str(status),
            lines=lines,
            attrs=_attrs(feature, optional_fields),
        ))
    return cables


def extract_gc(layer, id_field, state_field, label_field=None,
               optional_fields=None, target_authid=TARGET_CRS_AUTHID):
    """Extrait les artères GC d'une couche linéaire vers des ``GcArtere``.

    ``label_field`` (ex. ``nom``) sert de libellé si renseigné, sinon l'ID.
    """
    optional_fields = optional_fields or {}
    target = QgsCoordinateReferenceSystem(target_authid)
    transform = _transform_for(layer, target)

    gcs = []
    for feature in layer.getFeatures():
        lines = _lines_xy(feature.geometry(), transform)
        raw_id = feature[id_field]
        id_str = "" if raw_id is None else str(raw_id)
        label = id_str
        if label_field:
            value = feature[label_field]
            if value is not None and str(value).strip():
                label = str(value).strip()
        state = feature[state_field]
        gcs.append(GcArtere(
            id=id_str,
            label=label,
            state="" if state is None else str(state),
            lines=lines,
            attrs=_attrs(feature, optional_fields),
            fid=feature.id(),
        ))
    return gcs


def is_point_layer(layer):
    return layer is not None and layer.geometryType() == _POINT_GEOM


def is_line_layer(layer):
    return layer is not None and layer.geometryType() == _LINE_GEOM


# Correspondance (clé interne du résultat -> nom de champ shapefile, type).
# Les noms shapefile sont limités à 10 caractères (contrainte du format DBF).
SHP_FIELDS = [
    ("id_poteau", "id_poteau", "string"),
    ("commune", "commune", "string"),
    ("departement", "dept", "string"),
    ("territoire", "territoire", "string"),
    ("etat_poteau", "etat_pot", "string"),
    ("travaux", "travaux", "string"),
    ("nb_cables", "nb_cables", "integer"),
    ("etats_cables", "etats_cab", "string"),
    ("cables_associes", "cables", "string"),
    ("cables_non_tires", "cab_non_t", "string"),
    ("motif", "motif", "string"),
    ("rayon_buffer_m", "buffer_m", "double"),
    ("nb_cables_intersectes", "nb_inter", "integer"),
    ("mode_rattachement", "mode_ratt", "string"),
]


def export_poles_shapefile(path, rows, crs_authid=TARGET_CRS_AUTHID):
    """Écrit un shapefile ponctuel des poteaux sortis par l'analyse.

    Les géométries proviennent de la clé technique ``_xy`` des lignes résultat
    (déjà en EPSG:2154). Renvoie le nombre d'entités écrites.
    """
    from qgis.core import (
        QgsFeature, QgsGeometry, QgsPointXY, QgsVectorFileWriter,
    )

    # On déclare les types de champ directement dans l'URI de la couche
    # mémoire : robuste quelle que soit la version (pas de QVariant/QMetaType).
    uri_parts = ["Point?crs=" + crs_authid]
    for _, shp_name, shp_type in SHP_FIELDS:
        uri_parts.append("field={}:{}".format(shp_name, shp_type))
    mem = QgsVectorLayer("&".join(uri_parts), "poteaux_sans_cable_tire",
                         "memory")
    provider = mem.dataProvider()

    features = []
    for row in rows:
        feat = QgsFeature(mem.fields())
        xy = row.get("_xy")
        if xy is not None:
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(xy[0], xy[1])))
        for internal, shp_name, _ in SHP_FIELDS:
            feat.setAttribute(shp_name, row.get(internal))
        features.append(feat)
    provider.addFeatures(features)
    mem.updateExtents()

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "ESRI Shapefile"
    options.fileEncoding = "UTF-8"
    context = QgsProject.instance().transformContext()
    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        mem, path, context, options)
    # writeAsVectorFormatV3 renvoie un tuple dont le 1er élément est le code
    # d'erreur (0 = NoError quelle que soit la version).
    if int(result[0]) != 0:
        raise RuntimeError(result[1] or "Échec de l'écriture du shapefile.")
    return mem.featureCount()


# Champs du shapefile GC (nom <= 10 caractères, contrainte DBF).
GC_SHP_FIELDS = [
    ("id_gc", "id_gc", "string"),
    ("nom_gc", "nom_gc", "string"),
    ("commune", "commune", "string"),
    ("departement", "dept", "string"),
    ("territoire", "territoire", "string"),
    ("suivi_pilotage", "suivi", "string"),
    ("longueur", "longueur", "string"),
    ("longueur_gc_totale", "lgc_tot", "double"),
    ("longueur_couverte", "lgc_couv", "double"),
    ("ml_restant_optique", "ml_rest", "double"),
    ("seuil_reste_optique", "seuil_ml", "double"),
    ("nb_cables", "nb_cables", "integer"),
    ("etats_cables", "etats_cab", "string"),
    ("cables_associes", "cables", "string"),
    ("cables_non_tires", "cab_non_t", "string"),
    ("motif", "motif", "string"),
    ("rayon_buffer_m", "buffer_m", "double"),
    ("nb_cables_intersectes", "nb_inter", "integer"),
    ("mode_rattachement", "mode_ratt", "string"),
]


def export_gc_shapefile(path, rows, crs_authid=TARGET_CRS_AUTHID):
    """Écrit un shapefile linéaire des GC sortis par l'analyse.

    Les géométries proviennent de la clé technique ``_lines`` des lignes
    résultat (déjà en EPSG:2154). Renvoie le nombre d'entités écrites.
    """
    from qgis.core import (
        QgsFeature, QgsGeometry, QgsPointXY, QgsVectorFileWriter,
    )

    uri_parts = ["MultiLineString?crs=" + crs_authid]
    for _, shp_name, shp_type in GC_SHP_FIELDS:
        uri_parts.append("field={}:{}".format(shp_name, shp_type))
    mem = QgsVectorLayer("&".join(uri_parts), "gc_sans_cable_tire", "memory")
    provider = mem.dataProvider()

    features = []
    for row in rows:
        feat = QgsFeature(mem.fields())
        lines = row.get("_lines")
        if lines:
            multi = [[QgsPointXY(x, y) for (x, y) in line]
                     for line in lines if line]
            if multi:
                feat.setGeometry(QgsGeometry.fromMultiPolylineXY(multi))
        for internal, shp_name, _ in GC_SHP_FIELDS:
            feat.setAttribute(shp_name, row.get(internal))
        features.append(feat)
    provider.addFeatures(features)
    mem.updateExtents()

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "ESRI Shapefile"
    options.fileEncoding = "UTF-8"
    context = QgsProject.instance().transformContext()
    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        mem, path, context, options)
    if int(result[0]) != 0:
        raise RuntimeError(result[1] or "Échec de l'écriture du shapefile.")
    return mem.featureCount()
