"""Privacy-minimized presentation helpers for saved synthetic research reports."""

from __future__ import annotations

import html
import re


def _replace_common(text: str, replacements: dict[str, str]) -> str:
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(source, target)
    return re.sub(r"https?://(?:127\.0\.0\.1|localhost):\d+", "prototype:", text)


def _sanitize_markdown(text: str, replacements: dict[str, str], run_id: str) -> str:
    text = _replace_common(text, replacements)
    text = re.sub(r"(?m)^!\[[^\]]*\]\(artifacts/[^)]+\)\s*$\n?", "", text)
    text = re.sub(r"(?m)^- \*\*Relevant context\*\* \(profile\):.*\n", "", text)
    text = re.sub(r"(?ms)^## Not Included in Cross-Participant Themes\s*.*?(?=^## |\Z)", "", text)
    text = re.sub(r"(?ms)^## Appendix\s*.*\Z", "", text).rstrip() + "\n"
    notice = (
        "> Reviewed synthetic example. Full profiles, model requests, session identifiers "
        "and complete traces are intentionally excluded.\n"
    )
    return text.replace(f"Run: {run_id}\n", f"Source run: {run_id}\n\n{notice}", 1)


def _remove_html_section(text: str, title: str) -> str:
    escaped = re.escape(html.escape(title))
    text = re.sub(rf'<section(?: id="[^"]+")?><h2>{escaped}</h2>.*?</section>', "", text, flags=re.S)
    return re.sub(rf'<a href="#[^"]+">{escaped}</a>', "", text)


def _sanitize_html(text: str, replacements: dict[str, str], run_id: str) -> str:
    text = _replace_common(text, replacements)
    text = re.sub(r"<figure>.*?</figure>", "", text, flags=re.S)
    text = re.sub(r"<img\b[^>]*>", "", text, flags=re.S)
    text = re.sub(
        r'<dt><strong>Relevant context</strong> <span class="meta">profile</span></dt><dd>.*?</dd>',
        "",
        text,
        flags=re.S,
    )
    text = _remove_html_section(text, "Not Included in Cross-Participant Themes")
    text = _remove_html_section(text, "Appendix")
    notice = (
        '<p class="meta">Reviewed synthetic example. Full Persona profiles, model requests, '
        "session identifiers and complete traces are excluded.</p>"
    )
    return text.replace(f"<p>{run_id}</p>", f"<p>Source run: {run_id}</p>{notice}", 1)


def _standalone_html(text: str) -> str:
    return re.sub(
        r'<a href="artifacts/[^"#]+">(.*?)</a>',
        r'<span class="meta">\1</span>',
        text,
        flags=re.S,
    )
