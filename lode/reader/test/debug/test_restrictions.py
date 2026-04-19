import tempfile, os, pprint
from rdflib import Graph, BNode, Namespace
from rdflib.namespace import RDF, OWL, RDFS, XSD

from lode.reader import Reader
from lode.models import Quantifier

EX = Namespace("http://example.org/test#")


def make_quantifier_graph():
    g = Graph()
    g.bind("ex", EX)

    r_some       = BNode("r_some")
    r_all        = BNode("r_all")
    r_some_dtype = BNode("r_some_dtype")

    g.add((EX.MyClass,  RDF.type, OWL.Class))
    g.add((EX.myProp,   RDF.type, OWL.ObjectProperty))
    g.add((EX.Filler,   RDF.type, OWL.Class))
    g.add((EX.dataProp, RDF.type, OWL.DatatypeProperty))

    g.add((r_some, RDF.type,           OWL.Restriction))
    g.add((r_some, OWL.onProperty,     EX.myProp))
    g.add((r_some, OWL.someValuesFrom, EX.Filler))
    g.add((EX.MyClass, RDFS.subClassOf, r_some))

    g.add((r_all, RDF.type,           OWL.Restriction))
    g.add((r_all, OWL.onProperty,     EX.myProp))
    g.add((r_all, OWL.allValuesFrom,  EX.Filler))
    g.add((EX.MyClass, RDFS.subClassOf, r_all))

    g.add((r_some_dtype, RDF.type,           OWL.Restriction))
    g.add((r_some_dtype, OWL.onProperty,     EX.dataProp))
    g.add((r_some_dtype, OWL.someValuesFrom, XSD.integer))
    g.add((EX.MyClass, RDFS.subClassOf, r_some_dtype))

    return g


if __name__ == "__main__":
    g = make_quantifier_graph()

    tmp = tempfile.NamedTemporaryFile(suffix=".ttl", delete=False, mode="wb")
    tmp.write(g.serialize(format="turtle").encode())
    tmp.close()

    try:
        reader = Reader()
        reader.load_instances(tmp.name, "owl")

        viewer = reader.get_viewer()
        all_instances = viewer.get_all_instances()

        quantifiers = [i for i in all_instances if isinstance(i, Quantifier)]
        entities = viewer._format_entities(quantifiers)

        print(f"\n=== Quantifier entities ({len(entities)}) ===")
        for e in entities:
            print(f"\n  uri  : {e['uri']}")
            print(f"  type : {e['type']}")
            print(f"  label: {e['label']}")
            print(f"  relations:")
            for rel, values in e['relations'].items():
                print(f"    {rel}: {values}")

        assert len(entities) == 3, f"FAIL - attesi 3, trovati {len(entities)}"

        for e in entities:
            rels = e['relations']
            assert 'Quantifier Type'   in rels, f"FAIL - manca 'Quantifier Type' in {rels.keys()}"
            assert 'Applies On Property' in rels, f"FAIL - manca 'Applies On Property' in {rels.keys()}"
            assert 'Applies On Concept'  in rels, f"FAIL - manca 'Applies On Concept' in {rels.keys()}"

        print("\nOK - tutti i check passati")

    finally:
        os.unlink(tmp.name)
        