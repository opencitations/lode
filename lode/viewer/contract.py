"""The two steps of a page that are the same for every viewer (types in lode.viewer.view_data).

`to_model` assembles the header of the artefact; `resolve_links` fills in the address of every
link of a page once the page is complete, because only then is known which cards it holds.
"""
from typing import List, Optional

from lode.helpers.links import Links
from lode.viewer.view_data import Model, ViewData


def to_model(metadata: dict, export_formats: list, warnings: list) -> Model:
    """Build the contract Model from the header metadata, the export formats and the warnings.

    `metadata` is the dictionary the viewer builds for the header: `uri` and `label` are the
    identity of the artefact, `_namespaces` its prefixes, and every other key a field to show.
    It is empty when the source declares no ontology or concept scheme.
    """
    fields = dict(metadata)
    uri = fields.pop("uri", None)
    label = fields.pop("label", None)
    namespaces = fields.pop("_namespaces", [])

    return {
        "iri": uri[0]["iri"] if uri else None,
        "label": label[0]["text"] if label else None,
        "href": None,
        "metadata": fields,
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
    for entity in view["entities"]:
        to_page(entity, entity["iri"])          # its own page, never an anchor to itself
        for values in (*entity["relations"].values(), *entity["statements"].values()):
            for v in values:
                value(v)
