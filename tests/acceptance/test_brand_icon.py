# SPDX-License-Identifier: Apache-2.0
"""Acceptance tests — one Conversation Simulator icon, everywhere.

The project once carried four different marks at once: a teal plate with a
white bubble on the app bundle and the store logos, a purple one on the demo,
a capsule-only purple-and-green drawing on the Steam art, and an older cut of
the violet and emerald bubbles on the favicons. The official icon is
``docs/assets/brand/ConversationSimulatorIcon.svg``; everything else is drawn
from it by the studio's icon generator, which is kept with the store artwork
outside this repository.

test_demo_branding.py checks what each generated file looks like. These tests
check the rule itself, across the whole tree:

  * the two brand sources agree — mark.svg is the icon's bubbles, exactly;
  * any vector drawing in the repository that paints both voices, violet and
    emerald, is the official mark: it carries the source's own bubble paths;
  * none of the retired drawings survives in a vector file anyone could copy.

Pure Python, no renderer; it reads the tracked files only. Owner: platform team.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BRAND_DIR = _REPO_ROOT / "docs" / "assets" / "brand"
_ICON_SOURCE = _BRAND_DIR / "ConversationSimulatorIcon.svg"
_MARK_SOURCE = _BRAND_DIR / "mark.svg"

# Files that may embed an SVG drawing, inline or whole.
_VECTOR_SUFFIXES = {".svg", ".html", ".astro", ".tsx", ".jsx", ".mdx", ".vue"}
_YOU, _THEM = "#a78bfa", "#6ee7b7"

# The retired drawings, by a fragment no honest drawing of the official mark
# contains: the old 64-unit favicon's bubble rectangle, and the capsule-only
# mark's green bubble.  Plate colours are left to test_demo_branding.py, which
# reads pixels; as text they are ordinary colours.
_RETIRED_FRAGMENTS = (
    'width="36" height="26" rx="8"',      # the 64-unit favicon / logo mark
    'width="218" height="126" rx="26"',   # the capsule-only green bubble
)


def _tracked_vector_files() -> list[Path]:
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z"], cwd=_REPO_ROOT, check=True,
            capture_output=True, timeout=60,
        ).stdout.decode().split("\0")
    except (OSError, subprocess.SubprocessError):
        pytest.skip("not a git checkout: cannot list the tracked files")
    return [
        _REPO_ROOT / rel for rel in listed
        if rel and Path(rel).suffix in _VECTOR_SUFFIXES and (_REPO_ROOT / rel).is_file()
    ]


def _bubble_paths(body: str) -> list[str]:
    """The ``d`` of every path in an artwork body: the two bubbles' bodies."""
    return re.findall(r'<path[^>]*\sd="([^"]+)"', body)


def _view_box(svg: str) -> str:
    return re.search(r'viewBox="([^"]+)"', svg).group(1)


def _svg_blocks(text: str) -> list[str]:
    return re.findall(r"<svg\b.*?</svg>", text, re.S | re.I)


class TestTheSourcesAgree:
    def test_mark_is_the_icons_bubbles(self):
        """mark.svg is the icon without its square, not a second drawing."""
        icon, mark = _ICON_SOURCE.read_text(), _MARK_SOURCE.read_text()
        assert _view_box(icon) == _view_box(mark), "the two sources are drawn at different sizes"
        assert _bubble_paths(mark) == _bubble_paths(icon), (
            "docs/assets/brand/mark.svg's bubbles are not the icon's"
        )
        for colour in (_YOU, _THEM):
            assert colour in mark.lower() and colour in icon.lower()

    def test_the_icon_has_its_two_voices(self):
        assert len(_bubble_paths(_ICON_SOURCE.read_text())) == 2


class TestOneMarkEverywhere:
    def test_every_two_voice_drawing_is_the_official_mark(self):
        """A drawing in both voice colours carries the source's bubble paths.

        That is how a second logo would arrive — a hand-drawn favicon, a
        redrawn mark in a new page — and it is what this catches, wherever in
        the tree it lands.
        """
        official = _bubble_paths(_MARK_SOURCE.read_text())
        offenders = []
        for path in _tracked_vector_files():
            text = path.read_text(errors="replace")
            for block in _svg_blocks(text):
                lower = block.lower()
                if _YOU in lower and _THEM in lower and not all(d in block for d in official):
                    offenders.append(str(path.relative_to(_REPO_ROOT)))
                    break
        assert not offenders, (
            f"{offenders} draw a violet-and-emerald mark that is not "
            "docs/assets/brand/mark.svg; draw it from that file instead"
        )

    def test_no_retired_drawing_survives(self):
        offenders = [
            str(path.relative_to(_REPO_ROOT))
            for path in _tracked_vector_files()
            if any(f in path.read_text(errors="replace") for f in _RETIRED_FRAGMENTS)
        ]
        assert not offenders, f"{offenders} still carry a retired Conversation Simulator mark"
