import re

from django import template
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe


register = template.Library()
HTML_TAG_RE = re.compile(r"</?[a-z][^>]*>", re.IGNORECASE)
PARAGRAPH_BREAK_RE = re.compile(r"\r?\n\s*\r?\n+")
SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9«“])")
MISSING_SPACE_RE = re.compile(r"(?<=[.!?])(?=[A-ZÀ-ÖØ-Þ])")


@register.filter
def format_article_content(value, title=None):
    """Format plain-text article bodies while leaving authored HTML untouched."""
    content = str(value or "").strip()
    if not content:
        return ""

    if HTML_TAG_RE.search(content):
        return mark_safe(content)

    # Remove a duplicated title sometimes present at the start of imported bodies.
    title = str(title or "").strip()
    if title and content.casefold().startswith(title.casefold()):
        content = content[len(title):].lstrip(" \t\r\n:—-.")

    paragraphs = []
    for block in PARAGRAPH_BREAK_RE.split(content):
        block = re.sub(r"\s*\r?\n\s*", " ", block).strip()
        # In these articles, "ID. Nat" is an abbreviation, not a sentence boundary.
        block = re.sub(r"\bID\.", "ID§", block, flags=re.IGNORECASE)
        block = MISSING_SPACE_RE.sub(" ", block)
        sentences = [
            sentence.replace("§", ".").strip()
            for sentence in SENTENCE_BREAK_RE.split(block)
            if sentence.strip()
        ]
        for index in range(0, len(sentences), 2):
            paragraphs.append((" ".join(sentences[index:index + 2]), len(paragraphs) == 0))

    return format_html_join(
        "\n",
        "<p>{}</p>",
        ((text,) for text, _ in paragraphs),
    )
