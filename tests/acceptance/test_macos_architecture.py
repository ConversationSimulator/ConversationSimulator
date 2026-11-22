# SPDX-License-Identifier: Apache-2.0
"""Acceptance tests — what the docs say a Mac needs is what the build contains.

The shipped macOS build is one architecture, ``macOS-aarch64``: an Apple
Silicon bundle and nothing else. The docs used to promise Intel Macs as well
(issue #563), and an Intel Mac owner who installed from Steam got a binary that
would not run — the demo gate (D-09) forbids copy that claims what the build
does not do.

The binaries are built in the studio's publishing pipeline, outside this
repository, so the architectures it builds are restated here in
``_MACOS_BUILD_LEGS``. These tests fail when a document claims a Mac
architecture that list does not hold. When the pipeline gains an Intel or
universal leg, add it to the list; the check then turns itself off and the docs
can say Intel again.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The macOS legs of the studio's build matrix.
_MACOS_BUILD_LEGS = ("macOS-aarch64",)

# Every document here that states which Macs the Steam build runs on. The
# docs-site pages are hand-kept copies of the docs/ pages, so both are listed.
_CLAIM_FILES = (
    "docs/QA_STEAM_PLATFORM_MATRIX.md",
    "docs/STEAM_BETA_VERIFICATION_REPORT.md",
    "docs-site/src/content/docs/dev/qa-steam-platform-matrix.md",
    "docs-site/src/content/docs/dev/steam-beta-verification.md",
    "docs/platform-notes.md",
    "docs-site/src/content/docs/play/platform-notes.md",
    "docs/release-checklist.md",
    "docs-site/src/content/docs/dev/release-checklist.md",
    "docs/STEAM_ROADMAP.md",
    "docs-site/src/content/docs/dev/steam-roadmap.md",
    "docs/release-notes-template.md",
)

# Phrasings that promise an Intel Mac can run the Steam build. Deliberately
# narrow: "Intel Mac" in a sentence that says it is NOT supported is fine, and
# Intel CPUs in the Windows and Linux requirements are unrelated.
_INTEL_CLAIMS = (
    re.compile(r"Apple Silicon (?:\+|and|&) Intel", re.I),
    re.compile(r"Apple M\d+ or Intel", re.I),
    re.compile(r"\bmacOS\s*(?:—|-|\()\s*Intel\b.*\|\s*Required", re.I),
    re.compile(r"macOS \(Intel\)", re.I),
    re.compile(r"macOS \(Universal\)", re.I),
    re.compile(r"universal binary", re.I),
    re.compile(r"Apple Silicon[^|\n]{0,24}\bor Intel\b", re.I),
    re.compile(r"Apple M\d+\s*/\s*Intel\b", re.I),
    re.compile(r"\bmacOS\s*[—–-]\s*Intel\b", re.I),
    re.compile(r"\bIntel\s*=\s*x64\b", re.I),
    re.compile(r"_x64\.dmg\b", re.I),
)


def _macos_build_legs() -> list[str]:
    return list(_MACOS_BUILD_LEGS)


def _builds_intel(legs: list[str]) -> bool:
    return any(re.search(r"x86_64|x64|intel|universal", leg, re.I) for leg in legs)


@pytest.mark.parametrize("relpath", _CLAIM_FILES)
def test_docs_claim_only_the_macs_the_build_supports(relpath: str) -> None:
    legs = _macos_build_legs()
    if _builds_intel(legs):
        pytest.skip(f"the release builds {legs}: Intel claims are true")
    text = (_REPO_ROOT / relpath).read_text(encoding="utf-8")
    hits = [
        f"line {text.count(chr(10), 0, m.start()) + 1}: {m.group(0)!r}"
        for pattern in _INTEL_CLAIMS
        for m in pattern.finditer(text)
    ]
    assert not hits, (
        f"{relpath} says the Steam build runs on Intel Macs, but the release is built "
        f"for macOS only as {legs} (issue #563): " + "; ".join(hits)
    )
