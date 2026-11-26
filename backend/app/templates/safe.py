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
    "page_count",
    "age_rating",
    "content_warnings",
    "date_added",
    "book_url",
    "cover_url",
}
_VARIABLE_PATTERN = re.compile(r"{{\s*([a-z_]+)\s*}}")


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
