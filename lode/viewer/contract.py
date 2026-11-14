"""Translate what a viewer builds today into the types of the contract (lode.viewer.view_data).

The viewers still build their data in the older shape (BaseViewer.get_view_data). These functions
turn each piece of it into the contract, so that a template written from the contract can be shown
real data. As the viewers move to the contract this module shrinks, and it goes away.
"""
from typing import List, Optional

from lode.helpers.links import Links
from lode.viewer.view_data import Entity, Model, Nested, NestedPair, TreeNode, Value, ViewData

def _kind(link: Optional[str], external: bool) -> Optional[str]:
    """Return the kind of a link: None without one, "external" outside this documentation, else "page".

    The address (`href`) is not known here: the caller fills it in.
    """
    if not link:
        return None
    return "external" if external else "page"


def to_value(old: dict) -> Value:
    """Turn a value as the viewer builds it (text, link, lan, ...) into a contract Value."""
    link = old.get("link")
    return {
        "text": old.get("text"),
        "iri": link,
        "href": None,
        "kind": _kind(link, bool(old.get("is_external"))),
        "language": old.get("lan"),
        "type": old.get("type"),
        "deprecated": bool(old.get("is_deprecated")),
        "imported": bool(old.get("is_imported")),
        "visualize": None,
        "parts": [to_value(part) for part in (old.get("parts") or [])],
        "nested": _to_nested(old.get("nested")),
    }


def _to_pair(old: dict) -> NestedPair:
    """Turn one predicate and value of an annotation on an annotation."""
    return {"predicate": old["predicate"], "value": to_value(old.get("value") or {})}


def _to_nested(old: Optional[dict]) -> Optional[Nested]:
    """Turn the annotations carried by a statement value; None when it has none."""
    if not old:
        return None
    return {"main": _to_pair(old["main"]), "siblings": [_to_pair(p) for p in old["siblings"]]}


def to_entity(old: dict) -> Entity:
    """Turn a card as the viewer builds it into a contract Entity."""
    return {
        "iri": old["uri"],
        "type": old["type"],
        "label": old["label"],
        "anchor": old["anchor_id"],
        "href": None,
        "kind": "external" if old["is_external"] else "page",
        "deprecated": bool(old["is_deprecated"]),
        "relations": {name: [to_value(v) for v in values] for name, values in old["relations"].items()},
        "statements": {name: [to_value(v) for v in values] for name, values in old["statements"].items()},
        "characteristics": list(old["characteristics"]),
        "provenance": list(old["provenance"]),
    }


def to_tree_node(old: dict, type_name: str) -> TreeNode:
    """Turn a node of a section hierarchy; every node of a section has the section's type."""
    return {
        "iri": old["uri"],
        "type": type_name,
        "label": old["label"],
        "anchor": old["anchor_id"],
        "href": None,
        "kind": "page",
        "children": [to_tree_node(child, type_name) for child in old["children"]],
    }


def to_model(metadata: dict, export_formats: list, warnings: list, visualize) -> Model:
    """Build the contract Model from the header metadata, the export formats and the warnings.

    `metadata` is the dictionary the viewer builds for the header: `uri` and `label` are the
    identity of the artefact, `_namespaces` its prefixes, and every other key a field to show.
    It is empty when the source declares no ontology or concept scheme.
    """
    fields = dict(metadata)
    uri = fields.pop("uri", None)
    label = fields.pop("label", None)
    namespaces = fields.pop("_namespaces", [])

    def header(old: dict) -> Value:
        value = to_value(old)
        if old.get("is_visualizable") and old.get("link"):
            value["visualize"] = visualize(old["link"])
        return value

    return {
        "iri": uri[0]["link"] if uri else None,
        "label": label[0]["text"] if label else None,
        "href": None,
        "metadata": {name: [header(v) for v in values] for name, values in fields.items()},
        "namespaces": [{"prefix": n["prefix"], "uri": n["uri"]} for n in namespaces],
        "serializations": [{"label": f["label"], "fmt": f["fmt"], "ext": f["ext"],
                            "mime": f["mime"], "href": None} for f in export_formats],
        "warnings": [{"code": w["code"], "message": w["message"]} for w in warnings],
    }

def resolve_links(view: ViewData, links: Links) -> None:
    """Fill `href` and `kind` everywhere in `view`, in place.

    A link to a resource follows the first rule that applies: its card is on this very page, so it
    is an anchor; it belongs to this documentation, so it goes where `links` says; otherwise it is
    outside and goes to its own IRI. When `links` gives no address for a page of this documentation,
    the link has no `href` and no `kind`: it is plain text.
    """
    anchors = {}
    for entity in view["entities"]:
        anchors.setdefault(entity["iri"], entity["anchor"])

    def to_page(item, iri):
        href = links.resource(iri)
        item["href"], item["kind"] = href, ("page" if href else None)

    def point(item, iri, internal):
        if not iri:
            item["href"], item["kind"] = None, None
        elif iri in anchors:
            item["href"], item["kind"] = f"#{anchors[iri]}", "anchor"
        elif internal:
            href = links.resource(iri)
            item["href"], item["kind"] = (href, "page") if href else (iri, "external")
        else:
            item["href"], item["kind"] = iri, "external"

    def value(v):
        point(v, v["iri"], v["kind"] == "page")
        for part in v["parts"]:
            value(part)
        if v["nested"]:
            for pair in [v["nested"]["main"], *v["nested"]["siblings"]]:
                value(pair["value"])

    def nodes(items):
        for node in items:
            point(node, node["iri"], True)
            nodes(node["children"])

    model = view["model"]
    model["href"] = links.home()
    for serialization in model["serializations"]:
        serialization["href"] = links.export(serialization["ext"], view["focus"])
    for values in model["metadata"].values():
        for v in values:
            value(v)
    for section in view["toc"]:
        for entry in section["entities"]:
            point(entry, entry["iri"], True)
        nodes(section["tree"])
    for entity in view["entities"]:
        to_page(entity, entity["iri"])          # its own page, never an anchor to itself
        for values in (*entity["relations"].values(), *entity["statements"].values()):
            for v in values:
                value(v)
