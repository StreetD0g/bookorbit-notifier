"""A deliberately tiny interpolation engine that cannot evaluate Python or JavaScript."""

from __future__ import annotations

import re
from typing import Any

ALLOWED_TEMPLATE_VARIABLES = {
    "title",
    "subtitle",
    "authors",
    "series",
    "series_index",
    "series_tag",
    "library",
    "server",
    "genres",
    "language",
    "formats",
    "narrators",
    "duration",
    "description",
    "isbn",
    "publisher",
    "published_date",
    "published_year",
    "original_published_year",
    "isbn10",
    "isbn13",
    "tags",
    "collections",
    "edition_name",
    "rating",
    "duration_seconds",
    "audio_abridged",
    "date_updated",
    "page_count",
    "age_rating",
    "content_warnings",
    "date_added",
    "book_url",
    "cover_url",
}
_VARIABLE_PATTERN = re.compile(r"{{\s*([a-z_][a-z_0-9]*)\s*}}")
DEFAULT_SERIES_NUMBERED = "Teil {{series_index}} von {{series}}"
DEFAULT_SERIES_UNNUMBERED = "{{series}}"


def validate_series_format(template: str) -> None:
    """Limit nested series formats to source values and ordinary literal text."""

    if not template.strip() or len(template) > 512:
        raise ValueError("Series format must contain between 1 and 512 characters")
    validate_template_syntax(template, "Series format")
    if any(name not in {"series", "series_index"} for name in _VARIABLE_PATTERN.findall(template)):
        raise ValueError("Series format supports only series and series_index")


def validate_template_syntax(template: str, label: str) -> None:
    """Allow only documented `{{variable}}` interpolation with no control/code syntax."""

    if len(template) > 8_000:
        raise ValueError(f"{label} exceeds 8000 characters")
    if "{%" in template or "{#" in template:
        raise ValueError(f"{label} contains unsupported template syntax")
    variables = _VARIABLE_PATTERN.findall(template)
    if any(variable not in ALLOWED_TEMPLATE_VARIABLES for variable in variables):
        raise ValueError(f"{label} contains an unsupported template variable")
    remainder = _VARIABLE_PATTERN.sub("", template)
    if "{{" in remainder or "}}" in remainder:
        raise ValueError(f"{label} contains malformed template syntax")


def render_template(template: str, values: dict[str, Any]) -> str:
    """Render only validated variable tokens, converting missing values to an empty string."""

    validate_template_syntax(template, "Template")

    def replace(match: re.Match[str]) -> str:
        value = values.get(match.group(1))
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            return ", ".join(str(item) for item in value if item is not None)
        return str(value)

    return _VARIABLE_PATTERN.sub(replace, template)
