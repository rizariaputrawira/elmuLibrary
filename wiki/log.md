# Knowledge Base Compiler Log

Append-only chronological record of all ingestions, updates, lints, and refactor operations.

> [!TIP] Quick audit — recent entries:
> `grep "^## \[" wiki/log.md | tail -10`

## [2026-09-18] bootstrap | Initialized clean Karpathy LLM Wiki repository structure.
## [2026-09-18] update | Formalized strict versioning invariant and 7-field frontmatter schema across compiler directives and templates; mandatory user prompt if version is absent from source (`karpathy-template`, `article-template`).
## [2026-09-18] ingest | no material: raw/README.md
## [2026-09-18] refactor | Implemented 18 improvements from Karpathy spec gap analysis: added check_frontmatter.py + lint_wiki.py scripts; added Query Workflow + Lint Workflow + cross-reference rule to AGENTS.md; unified log format; fixed version fields in karpathy-template + index; added Version header to raw-template; fixed heading violations in llm-wiki-pattern + new-page template; added best-practices §§5–7 (ingest modes, web clipper, image handling); expanded index.md to 7 domains; added log.md grep tip; added Dataview + Marp plugins; configured raw/assets attachment path; wrote raw/README.md; updated .gitignore for pycache.
## [2026-09-18] refactor | Applied ponytail audit simplifications across scripts: replaced frozen dataclass with NamedTuple in check_evidence.py, removed redundant strip_fences and manual dedup loops, inlined label formatting, pruned duplicate is_empty_value entries and dead path prefixes, deleted unused stem(), and optimized slug resolution to O(1) in lint_wiki.py.
## [2026-11-16] refactor | Consolidated harness-agnostic rules into AGENTS.md and removed redundant core-ai-rules.md; added concept-hub-template.md and standardized frontmatter/provenance headers across templates; fixed frontmatter false-positives in check_evidence.py and raw wikilink resolution in lint_wiki.py; added blockquote sync checks in check_frontmatter.py, unified verify_all.py runner, and stdlib test suite in tests/test_scripts.py.
## [2026-11-16] refactor | Removed repository config, usage guides, and templates from wiki/ (deleted wiki/admin/); moved canonical templates into .obsidian/templates/ with templates.json; consolidated AI checklist into AGENTS.md and human usage guide into README.md; simplified verification scripts so wiki/ holds compiled knowledge only.
