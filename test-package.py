import lode
from lode import OwlOntology, SkosVocabulary
from lode.models import Concept

# 1. Leggere un artefatto
onto = OwlOntology("onto.ttl")                       # file locale
onto = OwlOntology("http://purl.org/spar/pwo/")      # URL
onto = OwlOntology("onto.ttl", imported=True)        # carica anche gli owl:imports
onto = OwlOntology("onto.ttl", warnings=True)        # raccoglie i warning del reader
voc = SkosVocabulary("vocabulary.ttl")

# 2. Ispezionare il contenuto
onto.instances()                                     # tutte le entità
onto.instances(Concept)                              # solo una classe del modello
onto.get_instance("http://example.org/o#A")          # entità di un IRI
onto.artefact_iri                                    # IRI dell'ontologia
onto.warnings                                        # problemi trovati
onto.graph                                           # grafo RDF
onto.main_graph()                                    # solo le triple dell'artefatto, senza gli import

# 3. Capire da dove viene un'entità
entity = next(iter(onto.get_instance("http://example.org/o#A")))
onto.provenance(entity)                              # triple da cui è nata
onto.reader                                           # logica del formato, per ispezione

# 4. Vedere cosa riceve il template
onto.viewer.view(language="en")                      # tutta la documentazione
onto.viewer.view(resource_uri="http://example.org/o#A", language="en")   # una risorsa

# 5. Esportare RDF
onto.viewer.export_main("turtle")                    # tutto l'artefatto
onto.viewer.export_resource("http://example.org/o#A", "turtle")          # una risorsa

# 6. Generare la documentazione
lode.build_site(onto, "site", lang="en")             # cartella di HTML statico

# 7. Scegliere il formato per nome (come fanno CLI e API)
onto = lode.read("onto.ttl", "owl")                  # restituisce OwlOntology