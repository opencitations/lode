import lode
from lode.reader import Reader
from lode.viewer import get_viewer

URL = "http://purl.org/spar/pwo/"

# A) via Reader, poi Artefact
reader = Reader()
reader.load_instances(URL, "owl", warnings=True)
artefact = reader.get_artefact()

print("type:", type(artefact).__name__)
print("read_as:", artefact.read_as)
print("artefact_iri:", artefact.artefact_iri)
print("istanze:", len(artefact.instances()))
print("warning:", len(artefact.warnings))
print("Reader pubblico:", sorted(m for m in dir(reader) if not m.startswith("_")))
print("Artefact pubblico:", sorted(m for m in dir(artefact) if not m.startswith("_")))

# B) stessa lettura via facade
art2 = lode.read(URL, "owl")
print("lode.read ->", type(art2).__name__, len(art2.instances()))

# C) viewer e ViewData
data = get_viewer(artefact).view(language="en")
print("ViewData keys:", list(data))
