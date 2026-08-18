"""Text helpers used across detection layers.

General-purpose, side-effect-free string utilities: normalization, ratio
helpers, and a generic label/value splitter. Domain-specific dictionaries
(identity labels, heading patterns) live with their consumers so this module
stays reusable.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator

# Pattern of "word" characters across scripts (letters + digits), used for ratios.
_NON_WORD = re.compile(r"[^\w]", re.UNICODE)
_WHITESAPE_RE = re.compile(r"\s+")
_ROMAN = re.compile(r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$", re.IGNORECASE)


def normalize(text: str | None) -> str:
    """Strip + collapse internal whitespace to single spaces. NFKC-normalized."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return _WHITESAPE_RE.sub(" ", text).strip()


def collapse(text: str | None) -> str:
    """Collapse whitespace without stripping (preserves leading/trailing for layout)."""
    if not text:
        return ""
    return _WHITESAPE_RE.sub(" ", text)


def is_blank(text: str | None) -> bool:
    """True when ``text`` is None or only whitespace."""
    return not text or not text.strip()


def letters(text: str) -> str:
    """Return only the letters/digits of ``text`` (no spaces/punct)."""
    return _NON_WORD.sub("", text or "")


def uppercase_ratio(text: str) -> float:
    """Fraction of cased letters in ``text`` that are uppercase (0.0–1.0)."""
    cased = [c for c in (text or "") if c.isalpha()]
    if not cased:
        return 0.0
    upper = sum(1 for c in cased if c.isupper())
    return upper / len(cased)


def word_count(text: str) -> int:
    """Approximate word count by whitespace splitting."""
    return len((text or "").split())


def shingles(text: str, k: int = 5) -> set[str]:
    """Return the set of word-k-shingles for ``text`` (lowercased words).

    Used by the leak detector to compare body content similarity without
    leaking full sentences into logs/external services.
    """
    words = normalize(text).lower().split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def is_roman_numeral(token: str) -> bool:
    """True when ``token`` looks like a roman numeral (I, II, IV, XII, …)."""
    token = (token or "").strip().upper()
    return bool(token) and len(token) <= 7 and bool(_ROMAN.match(token))


# --- generic label/value splitting -------------------------------------------

# A label is short, alphabetic text ending with ':' or '-'/'=' or a separator
# run before a value. Keeps it simple and predictable.
_LABEL_VALUE_RE = re.compile(
    r"""^\s*
        (?P<label>[^\s:][^:]{0,40}?)    # label text (no leading space, up to ~40 chars)
        \s*[:=\-]\s*                    # a single separator
        (?P<value>.+?)                  # the value
        \s*$
    """,
    re.VERBOSE,
)


def split_label_value(text: str) -> tuple[str, str] | None:
    """Split ``text`` into ``(label, value)`` if it matches a ``Label : value`` form.

    Returns ``None`` when there is no clear separator. This is the *generic*
    splitter; the identity-field mapping happens in the variable detector.
    """
    if not text:
        return None
    m = _LABEL_VALUE_RE.match(text)
    if not m:
        return None
    label = m.group("label").strip(" .:-")
    value = m.group("value").strip()
    if not label or not value:
        return None
    # Reject when "label" contains digits-heavy or is longer than the value by a lot
    # (likely not a label/value pair).
    if any(ch.isdigit() for ch in label) and not label.isascii():
        return None
    return label, value


def iter_chunks(seq: list, size: int) -> Iterator[list]:
    """Yield successive ``size``-sized chunks from ``seq`` (last may be shorter)."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]
