"""
Utility functions for the Mental Models tool.
"""
import re
import unicodedata


def canonicalize_name(name: str) -> str:
    """
    Turn a model/episode name into a canonical, DB-matchable form.

    Goals:
    - "Error Bars"              → "error bars"
    - "a powerful concept: Error Bars"  → "error bars"
    - "Error Bars: a powerful concept"  → "error bars"
    - "Today we're diving into the concept of Opportunity Costs."
        → "opportunity costs"
    - Strip generic fluff like "a powerful concept", "imagine you're...",
      "Today we're diving into...", etc.
    """
    if not name:
        return ""

    raw = unicodedata.normalize("NFKD", str(name))
    s = raw.lower().strip()

    connector_replacements = {
        "/": " and ",
        "&": " and ",
        "+": " and ",
    }
    for old, new in connector_replacements.items():
        s = s.replace(old, new)

    # Normalise some common phrasing
    s = s.replace(" versus ", " vs ")
    s = re.sub(r"\bvs\.\b", "vs", s)
    s = s.replace(" vs ", " vs ")

    # Strip some boilerplate podcast intro fragments
    s = re.sub(
        r"^(host:\s+)?welcome(?: back)? to mental models daily[:,]?\s*",
        "",
        s,
    )
    s = re.sub(
        r"^(today,?\s+we(?:'| a)re|today we(?:'| a)re)\s+"
        r"(?:diving into|examining|exploring|discussing|delving into|"
        r"focusing on|unraveling|looking at)\s+",
        "",
        s,
    )
    s = re.sub(
        r"\b(?:a|the|an|some|any|all|many|few|several|both|each|every|this|that|these|those|my|your|his|her|its|our|their|one|two|three|four|five|six|seven|eight|nine|ten)\b",
        " ",
        s,
    )
    s = re.sub(r"\s+", " ", s).strip()

    # Remove anything in parentheses or brackets
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\[[^\]]*\]", "", s)

    # Remove any remaining non-alphanumeric characters except spaces and hyphens
    s = re.sub(r"[^a-z0-9\s-]", " ", s)

    # Collapse multiple spaces and strip
    s = re.sub(r"\s+", " ", s).strip()

    return s
