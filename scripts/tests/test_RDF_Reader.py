"""
Test suite per RDFReader
"""

import sys
from pathlib import Path

# Aggiunge la cartella parent al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_base import Test


class TestRDFReader(Test):
    """Test per verificare il caricamento RDF da diverse fonti"""
    
    def run_all_tests(self):
        """Esegue tutti i test"""
        print("=" * 60)
        print("🚀 RDFReader Test Suite")
        print("=" * 60)
        
        root = Path(__file__).parent.parent

        self.test(
            "Custom onto | local | Turtle (Owl onto) |",
            "C:/Users/valep/Documents/GitHub/lode2/tests/data/owl_example_hereditary.ttl",
            should_work=True
        )
        
        self.test(
            "Pizza Ontology | Online Resource | OWL file (RDF/XML) |",
            "https://protege.stanford.edu/ontologies/pizza/pizza.owl",
            should_work=True
        )
        
        self.test(
            "Schema.org | Online Resource | JSON-LD | Note: Schema.org do not support content negotiation anymore",
            "https://schema.org/version/latest/schemaorg-current-https.jsonld",
            should_work=True
        )
        
        self.test(
            "Dublin Core Terms | Online Resource | No extension specified |",
            "http://purl.org/dc/terms/",
            should_work=True
        )
        
        self.test(
            "Pizza ontology | Local Resource | OWL (RDF/XML) |",
            str(root / "test" / "pizza.owl"),
            should_work=True
        )

        self.test(
            "Pizza ontology | Online Resource | OWL (RDF/XML) |",
            "https://protege.stanford.edu/ontologies/pizza/pizza.owl",
            should_work=True
        )
        
        self.test(
            "Invalid URL (with extension) | Online Resource | OWL |",
            "https://example.com/nonexistent.owl",
            should_work=False
        )

        self.test(
            "Invalid URI | Online Resource | OWL |",
            "https://example.com/",
            should_work=False
        )

        self.test(
            "SKOS vocabulary (defc.rdf) | Local Resource | RDF (rdf/xml)",
            str(root / "test" / "defc.rdf"),
            should_work=True
        )

        self.test(
            "HiCo ontology | Online resource | No extension specified |",
            "http://w3id.org/hico",
            should_work=True
        )

        self.test(
            "eFRBRoo | Online resource | No extension specified |",
            "http://erlangen-crm.org/efrbroo/",
            should_work=True
        )

        self.test(
            "Unavailable Resource (Hucit) | Online resource | No extension specified |",
            "http://purl.org/net/hucit#",
            should_work=False
        )

        self.test(
            "Cito | Online resource | No extension specified |",
            "http://purl.org/spar/cito",
            should_work=True
        )

        self.test(
            "WRITE thesaurus | Online resource | Turtle (skos vocab) |",
            "https://raw.githubusercontent.com/WenDAng-project/thesaurus/refs/heads/main/writeThesaurus_v.1.0.ttl",
            should_work=True
        )
        
        return self.print_summary()


if __name__ == "__main__":
    tester = TestRDFReader()
    all_passed = tester.run_all_tests()
    
    exit(0 if all_passed else 1)