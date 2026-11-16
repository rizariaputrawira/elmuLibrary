#!/usr/bin/env python3
"""Wiki health linter for a Karpathy-style LLM wiki.

Sweeps:
1. Broken wikilinks — [[wikilinks]] whose target does not resolve to a file in
   wiki/ (by stem, path, or frontmatter alias) or in raw/ (for raw source links).
2. Duplicate stems — compiled notes sharing the same filename stem.
3. Orphan notes — wiki notes that no other note links to via [[wikilink]].
   index.md, log.md, and *-index.md domain hubs are excluded.
4. Red links — concept slugs mentioned 2+ times across the wiki without a page.
5. Missing concept hubs — 2+ versioned notes sharing a stem (<slug>-v<ver>.md)
   without an unversioned concept hub ([[<slug>]]).
6. Unindexed notes — non-archived leaf notes not registered in
   wiki/index.md or any domain *-index.md catalog.
7. Log format — validates ## [YYYY-MM-DD] <action> | ... headers in wiki/log.md.

Exit code semantics:
- Returns 0 when 0 broken wikilinks are detected.
  (Other findings are reported as warnings.)
- Returns 1 when broken wikilinks are found (they break Obsidian navigation).

Usage: lint_wiki.py [project-root]
Defaults: project-root is current directory.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#][^\]]*)?\]\]")
VERSIONED_STEM_RE = re.compile(r"^(?P<stem>.+?)-v(?P<ver>\d+(?:[-_.]\d+)*)$")
FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
LOG_ENTRY_RE = re.compile(
    r"^## \[\d{4}-\d{2}-\d{2}\]\s+(?:bootstrap|ingest|update|refactor|archive|lint)\s*\|.+"
)
SKIP_ORPHAN_STEMS = {"index", "log"}


def iter_wiki_notes(wiki_dir: Path):
    yield from sorted(wiki_dir.rglob("*.md"))


def strip_fences_and_inline_code(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    return re.sub(r"`[^`\n]*`", " ", text)


def parse_wikilinks(text: str) -> list[str]:
    """Extract all [[wikilink]] targets from text, ignoring code blocks."""
    cleaned = strip_fences_and_inline_code(text)
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(cleaned)]


def parse_aliases(text: str) -> list[str]:
    """Extract aliases list from YAML frontmatter if present."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return []
    aliases: list[str] = []
    in_aliases = False
    for line in m.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("aliases:"):
            in_aliases = True
            val = stripped[len("aliases:") :].strip()
            if val.startswith("[") and val.endswith("]"):
                for item in val[1:-1].split(","):
                    clean = item.strip().strip("\"'").strip()
                    if clean:
                        aliases.append(clean)
                in_aliases = False
            continue
        if in_aliases:
            if stripped.startswith("- "):
                clean = stripped[2:].strip().strip("\"'").strip()
                if clean:
                    aliases.append(clean)
            elif stripped and not stripped.startswith("#"):
                in_aliases = False
    return aliases


def normalize_key(name: str) -> str:
    return re.sub(r"\s+", "-", name.strip().lower())


def is_raw_wikilink(slug: str) -> bool:
    """Return True if slug is a path targeting the raw/ directory."""
    clean = slug.strip()
    return clean.startswith("raw/") or "../raw/" in clean


def resolve_raw_link(slug: str, note: Path, root: Path) -> bool:
    """Verify that a raw/ wikilink resolves to an existing file inside raw/."""
    raw_root = (root / "raw").resolve()
    target = (root / slug).resolve() if slug.startswith("raw/") else (note.parent / slug).resolve()
    return target.is_relative_to(raw_root) and target.is_file()


def resolve_slug(slug: str, all_notes: dict[str, Path]) -> Path | None:
    """Return the .md path for a wiki slug or alias if it exists, else None."""
    clean = slug.strip()
    if clean.endswith(".md"):
        clean = clean[:-3]
    name = Path(clean).stem
    return (
        all_notes.get(clean)
        or all_notes.get(name)
        or all_notes.get(normalize_key(clean))
        or all_notes.get(normalize_key(name))
    )


def check_log_format(log_file: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, line) for malformed ## headings in wiki/log.md."""
    if not log_file.is_file():
        return []
    malformed: list[tuple[int, str]] = []
    in_fence = False
    for idx, line in enumerate(log_file.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if not in_fence and line.startswith("## ") and not LOG_ENTRY_RE.match(line):
            malformed.append((idx, line))
    return malformed


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    wiki_dir = root / "wiki"
    if not wiki_dir.is_dir():
        print(f"no wiki/ directory under {root}")
        return 1

    # Build slug/alias -> path map for all wiki notes
    all_notes: dict[str, Path] = {}
    stem_paths: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(wiki_dir.rglob("*.md")):
        rel = path.relative_to(wiki_dir).as_posix()
        rel_no_ext = rel[:-3] if rel.endswith(".md") else rel
        all_notes[rel_no_ext] = path
        all_notes[path.stem] = path
        norm_stem = normalize_key(path.stem)
        all_notes.setdefault(norm_stem, path)
        stem_paths[path.stem].append(path)
        for alias in parse_aliases(path.read_text(encoding="utf-8")):
            all_notes.setdefault(alias, path)
            all_notes.setdefault(normalize_key(alias), path)

    outbound: dict[Path, list[str]] = {}
    inbound: dict[str, list[str]] = defaultdict(list)
    mention_count: dict[str, int] = defaultdict(int)
    indexed_stems: set[str] = set()

    for note in iter_wiki_notes(wiki_dir):
        text = note.read_text(encoding="utf-8")
        links = parse_wikilinks(text)
        outbound[note] = links
        source_label = note.relative_to(wiki_dir).as_posix()
        is_index_hub = note.stem == "index" or note.stem.endswith("-index")

        for slug in links:
            if is_raw_wikilink(slug):
                continue
            target = resolve_slug(slug, all_notes)
            if target is not None:
                inbound[target.stem].append(source_label)
                if is_index_hub:
                    indexed_stems.add(target.stem)
            else:
                inbound[slug].append(source_label)
                mention_count[slug] += 1

    print("# Wiki health lint\n")

    # --- Sweep 1: Broken wikilinks ---
    print("## Broken wikilinks")
    broken_count = 0
    for note in sorted(iter_wiki_notes(wiki_dir)):
        broken = []
        for slug in outbound.get(note, []):
            if is_raw_wikilink(slug):
                if not resolve_raw_link(slug, note, root):
                    broken.append(slug)
                    broken_count += 1
            elif resolve_slug(slug, all_notes) is None:
                broken.append(slug)
                broken_count += 1
        if broken:
            label = note.relative_to(wiki_dir).as_posix()
            print(f"\n{label}")
            for slug in broken:
                print(f"  - [[{slug}]] → not found")
    if broken_count == 0:
        print("(none)")

    # --- Sweep 2: Duplicate stems ---
    print("\n## Duplicate note stems")
    dup_count = 0
    for stem, paths in sorted(stem_paths.items()):
        if len(paths) > 1:
            locs = ", ".join(p.relative_to(wiki_dir).as_posix() for p in paths)
            print(f"  - {stem}: {locs}")
            dup_count += 1
    if dup_count == 0:
        print("(none)")

    # --- Sweep 3: Orphan notes ---
    print("\n## Orphan notes (no inbound links)")
    orphan_count = 0
    for note in sorted(iter_wiki_notes(wiki_dir)):
        note_stem = note.stem
        if note_stem in SKIP_ORPHAN_STEMS or note_stem.endswith("-index"):
            continue
        if not inbound.get(note_stem):
            label = note.relative_to(wiki_dir).as_posix()
            print(f"  - {label}")
            orphan_count += 1
    if orphan_count == 0:
        print("(none)")
    else:
        print(f"\n⚠ {orphan_count} orphan note(s) — consider adding backlinks or registering in domain index")

    # --- Sweep 4: Red links (mentioned multiple times but no page) ---
    print("\n## Red links (mentioned 2+ times, no page exists)")
    red_count = 0
    for slug, count in sorted(mention_count.items(), key=lambda x: -x[1]):
        if count < 2:
            continue
        if resolve_slug(slug, all_notes) is None:
            print(f"  - [[{slug}]] — mentioned {count}× but no page exists")
            red_count += 1
    if red_count == 0:
        print("(none)")
    else:
        print(f"\n⚠ {red_count} red link(s) — consider creating stub pages")

    # --- Sweep 5: Missing concept hubs (2+ versioned notes sharing a stem) ---
    print("\n## Missing concept hubs")
    stem_groups: dict[str, list[str]] = defaultdict(list)
    for note in iter_wiki_notes(wiki_dir):
        m = VERSIONED_STEM_RE.match(note.stem)
        if m:
            stem_groups[m.group("stem")].append(note.stem)

    missing_hub_count = 0
    for stem, variants in sorted(stem_groups.items()):
        if len(variants) >= 2 and resolve_slug(stem, all_notes) is None:
            links = ", ".join(f"[[{v}]]" for v in sorted(variants))
            print(f"  - Concept '{stem}' has {len(variants)} versions ({links}) but lacks unversioned concept hub [[{stem}]]")
            missing_hub_count += 1
    if missing_hub_count == 0:
        print("(none)")
    else:
        print(f"\n⚠ {missing_hub_count} concept hub(s) missing — consider establishing unversioned concept hubs")

    # --- Sweep 6: Unindexed leaf notes ---
    print("\n## Unindexed leaf notes (not linked from index.md or *-index.md)")
    unindexed_count = 0
    for note in sorted(iter_wiki_notes(wiki_dir)):
        rel_parts = note.relative_to(wiki_dir).parts
        if (
            note.stem in SKIP_ORPHAN_STEMS
            or note.stem.endswith("-index")
            or "archive" in rel_parts
        ):
            continue
        if note.stem not in indexed_stems:
            print(f"  - {note.relative_to(wiki_dir).as_posix()}")
            unindexed_count += 1
    if unindexed_count == 0:
        print("(none)")
    else:
        print(f"\n⚠ {unindexed_count} unindexed note(s) — register in wiki/index.md or domain *-index.md")

    # --- Sweep 7: Log format check ---
    print("\n## Log format warnings")
    malformed_logs = check_log_format(wiki_dir / "log.md")
    for line_no, line in malformed_logs:
        print(f"  - wiki/log.md:{line_no}: malformed entry header: {line}")
    if not malformed_logs:
        print("(none)")

    print(
        f"\n## Summary\n"
        f"{broken_count} broken wikilink(s), {dup_count} duplicate stem(s), "
        f"{orphan_count} orphan(s), {red_count} red link(s), "
        f"{missing_hub_count} missing concept hub(s), {unindexed_count} unindexed note(s), "
        f"{len(malformed_logs)} log format warning(s)"
    )

    return 1 if broken_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
