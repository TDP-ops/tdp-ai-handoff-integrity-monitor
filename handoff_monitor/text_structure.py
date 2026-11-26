"""Versioned bounded UTF-8 line SHA-256 extractor for V0 text artifacts.

Locator grammar: line:<positive decimal index> (1-based, canonical).
Only LF-separated, BOM-free UTF-8 is supported. Hash exactly the UTF-8
bytes of that line, excluding its LF terminator. No normalization.
"""
import hashlib
import re
from pathlib import Path

TEXT_EXTRACTOR_ID = "tdp-text-utf8-line-sha256-v1"
LINE_LOCATOR = re.compile(r"line:([1-9][0-9]*)\Z", re.ASCII)
MAX_TEXT_BYTES = 8 * 1024 * 1024


def text_line_hash(path, locator):
    match = LINE_LOCATOR.fullmatch(locator)
    if match is None or len(match.group(1)) > 8:
        raise ValueError("Unsupported text segment locator")
    line_index = int(match.group(1))
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_TEXT_BYTES + 1)
    if len(raw) > MAX_TEXT_BYTES or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("Oversized or BOM-marked text")
    if b"\x00" in raw or b"\r" in raw:
        raise ValueError("Only UTF-8 text with LF separators is supported")
    raw.decode("utf-8", errors="strict")
    lines = raw.split(b"\n")
    if raw.endswith(b"\n"):
        lines.pop()  # A terminating LF is not an additional empty line.
    if line_index > len(lines):
        return None
    return hashlib.sha256(lines[line_index - 1]).hexdigest()
