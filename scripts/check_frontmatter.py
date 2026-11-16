#!/usr/bin/env python3
"""Frontmatter linter for a Karpathy-style LLM wiki.

Validates that every compiled wiki note contains all 7 mandatory YAML
frontmatter fields and that none are empty or missing.

Mandatory fields: title, tags, version, updated, sources, summary, aliases

Exit code semantics:
- Returns 0 when all checked notes pass.
- Returns 1 when any note has missing or empty mandatory fields.

Usage: check_frontmatter.py [project-root] [article.md ...]
Defaults: project-root is current directory; all wiki/**/*.md articles
except index.md and log.md are checked.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MANDATORY_FIELDS = ["title", "tags", "version", "updated", "sources", "summary", "aliases"]

# Same skip logic as check_evidence.py
SKIP_FILES = {"index.md", "log.md"}


GENERIC_VER_RE = re.compile(r"^(?:v?\d+(?:[._-]\d+)*(?:-[a-zA-Z0-9._-]+)?|meta)$")
POISON_VALUES = {"latest", "tbd", "current", "unknown", "none", "unreleased"}
FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*(\n|$)", re.DOTALL)


def is_empty_value(raw: str) -> bool:
    """Return True if a YAML value is effectively empty."""
    val = raw.strip()
    return val in ("", '""', "''", "[]")


def validate_version_syntax(val: str) -> bool:
    """Check if version string has valid syntax and is not a placeholder."""
    clean = val.strip().strip("\"'")
    if not clean or clean.lower() in POISON_VALUES or clean.startswith("{"):
        return False
    return GENERIC_VER_RE.match(clean) is not None


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Return a dict of frontmatter fields, or None if no valid frontmatter."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm_text = m.group(1)
    fields: dict[str, str] = {}
    current_key: str | None = None
    for line in fm_text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        # Top-level key: value
        m_line = re.match(r"^(\w[\w-]*):\s*(.*)", line)
        if m_line:
            current_key = m_line.group(1)
            fields[current_key] = m_line.group(2).strip()
        elif current_key and line.startswith(("  ", "\t")):
            # Continuation (multiline / list items) — append to current key
            fields[current_key] = (fields.get(current_key, "") + " " + line.strip()).strip()
    return fields


def parse_provenance_blockquote(text: str) -> dict[str, str]:
    """Extract Key: Value pairs from the blockquote immediately following the first H1."""
    body = FRONTMATTER_RE.sub("", text, count=1)
    state = "before_title"
    meta: dict[str, str] = {}
    for line in body.splitlines():
        stripped = line.strip()
        if state == "before_title":
            if line.startswith("# "):
                state = "after_title"
        elif state == "after_title":
            if not stripped:
                continue
            if stripped.startswith(">"):
                state = "header"
            else:
                break
        if state == "header":
            if not stripped.startswith(">"):
                break
            content = stripped.lstrip(">").strip()
            m_kv = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", content)
            if m_kv:
                meta[m_kv.group(1).lower()] = m_kv.group(2).strip()
    return meta


def check_note(path: Path) -> list[str]:
    """Return list of error strings for this note (empty = pass)."""
    text = path.read_text(encoding="utf-8")
    fields = parse_frontmatter(text)
    errors: list[str] = []
    if fields is None:
        return ["no YAML frontmatter found"]

    clean_version = fields.get("version", "").strip().strip("\"'")
    is_index = path.stem.endswith("-index")
    allow_empty_sources = is_index or clean_version == "meta"

    for field in MANDATORY_FIELDS:
        if field not in fields:
            errors.append(f"missing field: {field}")
        elif is_empty_value(fields[field]):
            if field == "sources" and allow_empty_sources:
                continue
            errors.append(f"empty field: {field}")

    # Version format validation
    if "version" in fields and not is_empty_value(fields["version"]):
        if not validate_version_syntax(clean_version):
            errors.append(f"invalid version format: '{clean_version}'")

    # Optional bundle_version validation
    clean_bundle = ""
    if "bundle_version" in fields and not is_empty_value(fields["bundle_version"]):
        clean_bundle = fields["bundle_version"].strip().strip("\"'")
        if not validate_version_syntax(clean_bundle) or clean_bundle == "meta":
            errors.append(f"invalid bundle_version format: '{clean_bundle}'")

    # Provenance blockquote consistency on compiled leaf notes
    blockquote = parse_provenance_blockquote(text)
    is_archived = "archive" in path.parts or "archived" in blockquote
    if not is_index and not is_archived:
        bq_version = blockquote.get("version", "").strip().strip("\"'")
        if not bq_version:
            errors.append("missing provenance header: > Version:")
        elif clean_version and bq_version != clean_version:
            errors.append(
                f"provenance > Version: '{bq_version}' does not match frontmatter version '{clean_version}'"
            )

        clean_updated = fields.get("updated", "").strip().strip("\"'")
        bq_updated = blockquote.get("updated", "").strip().strip("\"'")
        if not bq_updated:
            errors.append("missing provenance header: > Updated:")
        elif clean_updated and bq_updated != clean_updated:
            errors.append(
                f"provenance > Updated: '{bq_updated}' does not match frontmatter updated '{clean_updated}'"
            )

        if "sources" in fields and not is_empty_value(fields["sources"]):
            if not blockquote.get("raw", "").strip():
                errors.append("missing provenance header: > Raw:")

        if clean_bundle:
            bq_bundle = blockquote.get("bundle", "").strip().strip("\"'")
            if not bq_bundle:
                errors.append("missing provenance header: > Bundle:")
            elif bq_bundle != clean_bundle:
                errors.append(
                    f"provenance > Bundle: '{bq_bundle}' does not match frontmatter bundle_version '{clean_bundle}'"
                )

    return errors


def iter_notes(wiki_dir: Path):
    for path in sorted(wiki_dir.rglob("*.md")):
        rel = path.relative_to(wiki_dir).as_posix()
        if rel in SKIP_FILES:
            continue
        yield path


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    wiki_dir = root / "wiki"
    if not wiki_dir.is_dir():
        print(f"no wiki/ directory under {root}")
        return 1

    notes = []
    for arg in argv[2:]:
        path = Path(arg)
        if not path.is_absolute():
            path = root / path
        if path.is_file():
            notes.append(path)
        else:
            print(f"warning: not found: {arg}", file=sys.stderr)

    if len(argv) <= 2:
        notes = list(iter_notes(wiki_dir))

    print("# Frontmatter lint\n")
    error_count = 0
    checked = 0
    for note in notes:
        checked += 1
        errors = check_note(note)
        if errors:
            label = note.resolve().relative_to(root) if note.resolve().is_relative_to(root) else note
            print(f"\n{label}")
            for err in errors:
                print(f"  - {err}")
            error_count += 1

    if error_count == 0:
        print(f"(none) — {checked} note(s) checked, all pass")
    else:
        print(f"\n{error_count} note(s) with frontmatter issues (of {checked} checked)")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
