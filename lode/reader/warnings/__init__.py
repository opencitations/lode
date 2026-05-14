"""
Warnings package — format-specific warning checks for Semantic Artefact logics.

Each module exposes free functions that take a `logic` instance as first arg
and push messages via `logic.add_warning(code, subject, message)`.

Pipeline-time checks are called inline from the corresponding *_logic module;
post-pipeline checks are entry-pointed via `<format>_warnings.run_post_checks(logic)`.
"""

from lode.reader.warnings import owl_warnings

__all__ = [
    'owl_warnings',
]