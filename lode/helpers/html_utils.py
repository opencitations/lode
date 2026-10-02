# lode/helpers/html_utils.py
"""HTML post-processing utilities.

Shared by api.py (HTTP responses) and builder.py (static site generation).
No dependency on FastAPI or any HTTP layer.
"""
import re
import minify_html


def minify(html: str) -> str:
    """Minify HTML preserving render-markdown blocks (newline-sensitive).

    render-markdown blocks contain Markdown text rendered client-side:
    stripping their newlines would break the Markdown parser. They are
    stashed before minification and restored verbatim afterwards.
    """
    stash: list[str] = []

    def _hold(m: re.Match) -> str:
        stash.append(m.group(0))
        return f"\x00MD{len(stash)-1}\x00"

    protected = re.sub(
        r'<(span|div|a|p)\b[^>]*\brender-markdown\b[^>]*>.*?</\1>',
        _hold, html, flags=re.S,
    )
    out = minify_html.minify(protected, minify_css=False, minify_js=False)
    for i, block in enumerate(stash):
        out = out.replace(f"\x00MD{i}\x00", block)
    return out