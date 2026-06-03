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
    QgsWkbTypes,
)

from .core.models import Pole, Cable

TARGET_CRS_AUTHID = "EPSG:2154"


def list_vector_layers():
    """Renvoie les couches vecteur du projet courant (objets QgsVectorLayer)."""
    layers = []
    for layer in QgsProject.instance().mapLayers().values():
        # Test de canard : on garde ce qui ressemble à une couche vecteur.
        if hasattr(layer, "fields") and hasattr(layer, "getFeatures"):
            if layer.type() == layer.VectorLayer:
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
    """Construit le dict d'attributs optionnels (commune/dept/territoire)."""
    attrs = {}
    for key in ("commune", "departement", "territoire"):
        field = mapping.get(key)
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


def is_point_layer(layer):
    return layer is not None and QgsWkbTypes.geometryType(
        layer.wkbType()) == QgsWkbTypes.PointGeometry


def is_line_layer(layer):
    return layer is not None and QgsWkbTypes.geometryType(
        layer.wkbType()) == QgsWkbTypes.LineGeometry
