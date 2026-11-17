from lode.profiles.owl.artefact import OwlOntology
from lode.profiles.skos.artefact import SkosVocabulary
from lode.models import Concept
import lode

# 1. Leggere un artefatto
                       # file locale
onto = OwlOntology("http://purl.org/spar/pwo/")      # URL
print(onto)
