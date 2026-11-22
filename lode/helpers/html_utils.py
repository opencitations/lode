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
        """Replace a protected block with a numbered placeholder and remember the block."""
        stash.append(m.group(0))
        return f"\x00MD{len(stash)-1}\x00"

    protected = re.sub(
        r'<(span|div|a|p)\b[^>]*\brender-markdown\b[^>]*>.*?</\1>',
        _hold, html, flags=re.S,
    )
    
    def _restore(m: re.Match) -> str:
        """Return the protected block that a placeholder stands for."""
        return stash[int(m.group(1))]

    out = minify_html.minify(protected, minify_css=False, minify_js=False)
    # One pass: replacing block by block rescanned the whole page once per block.
    return re.sub(r"\x00MD(\d+)\x00", _restore, out)