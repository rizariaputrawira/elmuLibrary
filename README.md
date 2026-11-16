# 🧠 Elmu Library
**`Harness-Agnostic Knowledge Library based on Karpathy LLM Wiki`**

A persistent, compounding personal knowledge base built on the **Andrej Karpathy LLM Wiki Pattern**.

Instead of performing query-time retrieval against unorganized document dumps, an AI assistant continuously compiles, interlinks, and maintains a structured, dense Markdown wiki grounded in immutable primary sources. All agent directives live in [AGENTS.md](AGENTS.md) so the vault works across any coding or AI agent harness.

---

## 📂 Repository Architecture

```
.
├── AGENTS.md                 # Harness-agnostic compiler directives & operating rules
├── README.md                 # Knowledge base architecture overview
│
├── 🧠 wiki/                   # Compiled Knowledge Base (Dense Markdown Network)
│   ├── index.md              # Master domain navigation hub (7 domain catalogs)
│   ├── log.md                # Chronological append-only compiler operations ledger
│   ├── <domain>/             # Compiled domain articles & concept hubs (wiki/<domain>/<slug>.md)
│   ├── archive/              # Historical, point-in-time archived snapshots
│   └── admin/                # Pattern specifications & templates
│       ├── admin-index.md    # Index of administrative notes & templates
│       ├── meta/             # Pattern definitions (LLM Wiki, Karpathy standard, best practices)
│       └── references/       # Canonical templates (article, concept-hub, raw, index, archive)
│
├── 📥 raw/                    # Immutable Primary Sources (Grounding Tier)
│   ├── README.md             # Raw source drop-zone specification & naming conventions
│   ├── <topic>/              # Domain-specific primary sources (YYYY-MM-DD-slug.md/.pdf/.txt)
│   └── assets/               # Downloaded images (Obsidian attachment folder)
│
├── ⚡ scripts/                # Automated verification tooling (pure Python stdlib)
│   ├── verify_all.py         # Unified runner executing all three verification checks
│   ├── check_frontmatter.py  # Validates 7-field frontmatter, version syntax & blockquote sync
│   ├── lint_wiki.py          # Checks wikilinks (incl. raw/), orphans, red links, concept hubs & log
│   └── check_evidence.py     # Mechanical evidence check enforcing the Grounding Invariant
│
└── 🧪 tests/                  # Automated unit & regression tests (pure Python unittest)
    └── test_scripts.py       # Test suite for verification scripts
```

---

## 🧭 Core Operations & Operating Principles

1. **The Grounding Invariant**: Every load-bearing factual claim in `wiki/` (specific numbers, dates, direct quotes) must exist verbatim in an immutable source file under `raw/`.
2. **4-Stage Ingestion Pipeline**:
   - **Fetch**: Store raw document in `raw/<topic>/YYYY-MM-DD-slug.md` (or `.pdf`/`.txt`) with provenance metadata.
   - **Triage & Version Gate**: Search `wiki/` for existing related topics. Confirm `version` (and optional `bundle_version` when the source bundle differs from the subject component); stop and ask the user if ambiguous.
   - **Compile**: Synthesize dense, structured markdown notes at `wiki/<domain>/<slug>.md` following `[[karpathy-template]]` with 7-field YAML frontmatter and `[[wikilinks]]`. When $\ge 2$ divergent versions exist (`<slug>-v<ver>.md`), maintain an unversioned **Concept Hub** (`<slug>.md`, `version: "meta"`).
   - **Log**: Append a canonical entry in `wiki/log.md` recording the operation.
3. **Query & Compound**: Read `wiki/index.md`, drill into compiled notes, and file valuable cross-source syntheses back into `wiki/` as permanent notes.
4. **Lint & Maintain**: Periodically verify frontmatter, links, unindexed pages, log formatting, and grounding fidelity.

---

## 🛠️ Verification & Test Tooling

Run the entire verification suite with one command:

```bash
python3 scripts/verify_all.py .
```

Or run individual checks and the unit test suite:

```bash
python3 scripts/check_frontmatter.py .
python3 scripts/lint_wiki.py .
python3 scripts/check_evidence.py .
python3 -m unittest discover -s tests -v
```
