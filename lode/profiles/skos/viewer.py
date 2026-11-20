"""Viewer for SKOS artefacts."""

from typing import List, Optional

# internal imports
from lode.viewer.view_data import TocEntry, TocSection, ViewData
from lode.helpers.links import Links
from lode.viewer.base_viewer import BaseViewer


class TreeNode(TocEntry):
    """One node of the concept taxonomy: a concept and the concepts narrower than it."""

    children: List["TreeNode"]


class SkosTocSection(TocSection):
    """A section of the SKOS navigation: the base one plus the taxonomy of its concepts.

    The section of the collections has an empty `tree`.
    """

    tree: List[TreeNode]



class SkosViewer(BaseViewer):
    """SKOS viewer.

    Display names, table of contents and card come from the viewer.yaml of this profile.
    Entities are formatted by BaseViewer, so SKOS produces the same data structure
    as OWL and the card (a separate template) reads the same keys.
    """

    def view(self, resource_uri: Optional[str] = None, language: Optional[str] = None,
             links: Optional[Links] = None) -> ViewData:
        """SKOS viewer.

        Display names and table of contents come from viewer.yaml. Entities are
        formatted by BaseViewer, so SKOS produces the same data structure as OWL. It adds the
        taxonomy of the concepts, which its own sidebar (templates/_toc.html of this profile) draws.
        """

        data = super().view(resource_uri, language, links)
        for section in data['toc']:
            addresses = {e['iri']: (e['href'], e['kind']) for e in section['entries']}
            self._copy_addresses(section['tree'], addresses)
        return data

    def _copy_addresses(self, nodes: List[TreeNode], addresses: dict) -> None:
        """Give each node, and the nodes below it, the address of the entry that has its IRI."""
        for node in nodes:
            node['href'], node['kind'] = addresses[node['iri']]
            self._copy_addresses(node['children'], addresses)

    def _build_toc(self, language: str) -> List[TocSection]:
        """Build the navigation, with the taxonomy of the concepts added to the sections.

        Every section gets a `tree` (empty for the ones that have no hierarchy, such as the
        collections), so the SKOS sidebar can read it without checking that it exists.
        """
        toc = super()._build_toc(language)
        concepts = [i for i in self.get_toc_entities() if type(i).__name__ == 'Concept']
        for section in toc:
            section['tree'] = self._build_taxonomy(concepts, language) if section['type'] == 'Concept' else []
        return toc

    def _build_taxonomy(self, concepts: List, language: Optional[str]) -> List[TreeNode]:
        """Build the forest of the concepts, each one under its broader concepts.

        A concept with several broader concepts appears under each of them, which is how a
        SKOS taxonomy works; one whose broader concepts are not documented here is a root.
        A cycle is cut where it closes, so a malformed vocabulary cannot loop forever.
        """
        by_iri = {str(c.has_identifier): c for c in concepts if getattr(c, 'has_identifier', None)}
        narrower = {iri: [] for iri in by_iri}
        has_parent = set()
        for iri, concept in by_iri.items():
            for broader in concept.get_is_sub_concept_of() or []:
                parent = str(getattr(broader, 'has_identifier', '') or '')
                if parent in by_iri and parent != iri:
                    narrower[parent].append(iri)
                    has_parent.add(iri)

        def label_key(iri: str) -> str:
            """Sort key of a concept: its label, or its IRI when it has none."""
            return (self._get_best_label(by_iri[iri], language) or iri).lower()

        def node(iri: str, path: frozenset) -> Optional[TreeNode]:
            """Build the node of a concept with its narrower ones; None when it closes a cycle."""
            if iri in path:
                return None
            entry = self._toc_entry(by_iri[iri], language)
            kids = (node(child, path | {iri}) for child in sorted(narrower[iri], key=label_key))
            return {**entry, 'label': entry['label'] or iri, 'children': [k for k in kids if k]}

        roots = (node(iri, frozenset()) for iri in sorted((i for i in by_iri if i not in has_parent),
                                                          key=label_key))
        return [r for r in roots if r]
