#!/usr/bin/env python3
"""Unit and regression tests for wiki verification scripts."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_evidence
import check_frontmatter
import lint_wiki
import verify_all


def run_silently(fn, argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(argv)
    return rc, buf.getvalue()


class WikiScriptsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "raw" / "ai-ml").mkdir(parents=True)
        (self.root / "wiki" / "ai-ml").mkdir(parents=True)

        (self.root / "raw" / "README.md").write_text("# Raw drop-zone\n", encoding="utf-8")
        (self.root / "wiki" / "index.md").write_text(
            "---\n"
            'title: "Knowledge Index"\n'
            "tags: [index]\n"
            'version: "meta"\n'
            "updated: 2026-11-16\n"
            "sources: []\n"
            'summary: "Master navigation index."\n'
            'aliases: ["index"]\n'
            "---\n\n"
            "# Knowledge Index\n\n"
            "- [[attention]]: Transformer attention.\n",
            encoding="utf-8",
        )
        (self.root / "wiki" / "log.md").write_text(
            "# Log\n\n## [2026-11-16] bootstrap | Initialized test vault.\n",
            encoding="utf-8",
        )
        (self.root / "raw" / "ai-ml" / "2026-01-01-paper.md").write_text(
            "# Attention Paper\n\n"
            "> Source: https://example.org/paper\n"
            "> Collected: 2026-01-01\n"
            "> Published: 2017-06-12\n"
            "> Version: 1.0.0\n\n"
            "The model achieves 28.4 BLEU on WMT 2014 English-to-German.\n"
            '"Scaled Dot-Product Attention computes the dot products of the query."\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_valid_article(self) -> Path:
        article = self.root / "wiki" / "ai-ml" / "attention.md"
        article.write_text(
            "---\n"
            'title: "Attention Mechanism"\n'
            "tags: [ai-ml, transformers]\n"
            'version: "1.0.0"\n'
            "updated: 2026-11-16\n"
            'sources: ["raw/ai-ml/2026-01-01-paper.md"]\n'
            'summary: "Synthesis of scaled dot-product attention with 28.4 BLEU benchmark."\n'
            'aliases: ["scaled-attention"]\n'
            "---\n\n"
            "# Attention Mechanism\n\n"
            "> Version: 1.0.0\n"
            "> Raw: [[../../raw/ai-ml/2026-01-01-paper.md]]\n"
            "> Updated: 2026-11-16\n\n"
            "Up: [[index]]\n\n"
            "Achieves 28.4 BLEU in 2014 as described:\n"
            '"Scaled Dot-Product Attention computes the dot products of the query."\n',
            encoding="utf-8",
        )
        return article

    def test_valid_article_passes_all_checks(self) -> None:
        self._write_valid_article()
        rc, out = run_silently(verify_all.main, ["verify_all", str(self.root)])
        self.assertEqual(rc, 0, msg=out)
        self.assertIn("0 fidelity suspect(s), 0 evidence error(s), 0 unreferenced raw file(s)", out)
        self.assertIn("0 broken wikilink(s)", out)

    def test_check_evidence_ignores_frontmatter_and_raw_readme(self) -> None:
        # Frontmatter summary has >15 chars and updated: 2026-11-16 which are NOT in raw/
        self._write_valid_article()
        rc, out = run_silently(check_evidence.main, ["check_evidence", str(self.root)])
        self.assertEqual(rc, 0, msg=out)
        self.assertIn("0 fidelity suspect(s)", out)
        self.assertIn("0 unreferenced raw file(s)", out)

    def test_check_evidence_flags_ungrounded_body_claim(self) -> None:
        article = self._write_valid_article()
        article.write_text(
            article.read_text(encoding="utf-8") + "\nHallucinated metric: 99.99% accuracy.\n",
            encoding="utf-8",
        )
        rc, out = run_silently(check_evidence.main, ["check_evidence", str(self.root)])
        self.assertEqual(rc, 0, msg=out)
        self.assertIn("1 fidelity suspect(s)", out)
        self.assertIn("99.99%", out)

    def test_check_frontmatter_validates_versions_and_blockquote_sync(self) -> None:
        article = self._write_valid_article()
        # Pre-release and ISO versions should pass
        text = article.read_text(encoding="utf-8")
        for ver in ("1.2.0-rc.1", "2026-03-15"):
            article.write_text(
                text.replace('version: "1.0.0"', f'version: "{ver}"').replace(
                    "> Version: 1.0.0", f"> Version: {ver}"
                ),
                encoding="utf-8",
            )
            rc, out = run_silently(check_frontmatter.main, ["check_frontmatter", str(self.root)])
            self.assertEqual(rc, 0, msg=out)

        # Mismatched provenance blockquote should fail
        article.write_text(
            text.replace("> Updated: 2026-11-16", "> Updated: 2026-01-01"),
            encoding="utf-8",
        )
        rc, out = run_silently(check_frontmatter.main, ["check_frontmatter", str(self.root)])
        self.assertEqual(rc, 1, msg=out)
        self.assertIn("does not match frontmatter updated", out)

        # Poison version "latest" should fail
        article.write_text(
            text.replace('version: "1.0.0"', 'version: "latest"').replace(
                "> Version: 1.0.0", "> Version: latest"
            ),
            encoding="utf-8",
        )
        rc, out = run_silently(check_frontmatter.main, ["check_frontmatter", str(self.root)])
        self.assertEqual(rc, 1, msg=out)
        self.assertIn("invalid version format", out)

    def test_lint_wiki_broken_link_and_missing_concept_hub(self) -> None:
        article = self._write_valid_article()
        # Add broken wikilink
        article.write_text(
            article.read_text(encoding="utf-8") + "\nSee [[non-existent-page]].\n",
            encoding="utf-8",
        )
        rc, out = run_silently(lint_wiki.main, ["lint_wiki", str(self.root)])
        self.assertEqual(rc, 1, msg=out)
        self.assertIn("[[non-existent-page]] → not found", out)

        # Replace broken link with two versioned siblings lacking a concept hub
        article.unlink()
        for ver in ("v1", "v2"):
            (self.root / "wiki" / "ai-ml" / f"raft-{ver}.md").write_text(
                f"---\ntitle: \"Raft {ver}\"\ntags: [cs]\nversion: \"{ver[1:]}.0.0\"\n"
                "updated: 2026-11-16\nsources: [\"raw/ai-ml/2026-01-01-paper.md\"]\n"
                f'summary: "Raft {ver} notes."\naliases: ["raft-{ver}"]\n---\n\n'
                f"# Raft {ver}\n\n> Version: {ver[1:]}.0.0\n> Raw: [[../../raw/ai-ml/2026-01-01-paper.md]]\n> Updated: 2026-11-16\n",
                encoding="utf-8",
            )
        (self.root / "wiki" / "index.md").write_text(
            "# Index\n\n- [[raft-v1]]\n- [[raft-v2]]\n",
            encoding="utf-8",
        )
        rc, out = run_silently(lint_wiki.main, ["lint_wiki", str(self.root)])
        self.assertEqual(rc, 0, msg=out)
        self.assertIn("lacks unversioned concept hub [[raft]]", out)


if __name__ == "__main__":
    unittest.main()
