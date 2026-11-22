# SPDX-License-Identifier: Apache-2.0
"""Acceptance tests — demo-edition branding (issue #499, demo gate D-10).

The Steam Demo app (5343430) once shipped the base app's icon because
``tauri.demo.conf.json`` overlaid the product name but not ``bundle.icon``, so
the demo and the full game were indistinguishable in the Steam client. Later
the two editions were told apart by two different plates, teal and purple,
around a white bubble that was not the brand's mark at all. Now there is one
icon, ``docs/assets/brand/ConversationSimulatorIcon.svg``, and the demo is that
icon with an amber "DEMO" badge in its lower-right corner. These tests pin it:

  * the demo overlay overrides every icon the base config declares, and each
    override resolves to a real file;
  * every base frame draws the official icon — its two voices, violet and
    emerald, where the source puts them, on its dark stage — and every demo
    frame is that same frame, pixel for pixel, except inside the badge, which
    is amber with four dark letterforms in it. At 16-32 px the word is mush,
    but the amber pill is still there: colour is what tells two rows of a
    library list apart;
  * the hand-written ICO and ICNS containers carry every representation a
    desktop asks for, each one holds the size its directory entry or chunk
    type promises, the ICNS is on Apple's icon grid, and the run-length
    encoded ARGB chunks decode to the frame they were built from.

These are the icons the app itself is built with. The store artwork drawn from
the same icon (the Steamworks icons and capsules, the Microsoft Store logos)
and the generator that draws all of it are kept with the store files, outside
this repository, and are checked there.

Nothing here needs a build, a renderer or a network: the PNGs, the ICO and the
ICNS are parsed directly. Owner: platform team.
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_TAURI = _REPO_ROOT / "apps" / "desktop" / "src-tauri"
_BASE_CONF = _SRC_TAURI / "tauri.conf.json"
_DEMO_CONF = _SRC_TAURI / "tauri.demo.conf.json"
_BUNDLE_DIR = {"base": _SRC_TAURI / "icons", "demo": _SRC_TAURI / "icons-demo"}
_EDITIONS = ("base", "demo")

# The brand palette (docs/brand.md), restated so that a recoloured source or
# badge fails here rather than shipping.
_YOU = (0xA7, 0x8B, 0xFA)       # --cs-you, the violet bubble
_THEM = (0x6E, 0xE7, 0xB7)      # --cs-them, the emerald bubble
_BADGE = (0xFB, 0xBF, 0x24)     # --cs-event, the DEMO pill
_INK = (0x0F, 0x0F, 0x11)       # --cs-stage, the DEMO lettering
_STAGE_LIGHT = (0x45, 0x45, 0x45)   # the icon's radial gradient, centre ...
_STAGE_DARK = (0x29, 0x29, 0x29)    # ... and edge
# Colours that must appear nowhere in any icon any more: the old teal and
# purple plates, and the old capsule-only green bubble.
_RETIRED = ((0x14, 0x7A, 0x84), (0x6D, 0x28, 0xD9), (0x15, 0x80, 0x3D))

# Where the two bubbles are solid, as fractions of the icon's side, read off
# the 864-unit source: the middle of each bubble's body.
_YOU_AT = (0.25, 0.52)
_THEM_AT = (0.72, 0.33)

# The badge's rectangle, as fractions of the icon's side, restated from the
# icon generator (an 88-unit cap height of a 4.1725-cap-wide word, 44 units of
# padding either side, a 150-unit pill, 52 units off the right and bottom
# edges, all of 864) so that moving the badge without meaning to is a failure.
_BADGE_H = 150 / 864
_BADGE_W = (88 * 4.1725 + 2 * 44) / 864
_BADGE_MARGIN = 52 / 864


# ---------------------------------------------------------------------------
# Minimal PNG reader — enough for the 8-bit RGBA icons this repo generates.
# ---------------------------------------------------------------------------
def _read_png(path: Path) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """Return (width, height, RGBA pixels) for an 8-bit truecolour-alpha PNG."""
    return _decode_png(path.read_bytes(), path)


def _decode_png(raw: bytes, path: object) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """As ``_read_png``, for PNG bytes already in hand (an ICO frame)."""
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    pos, idat, header = 8, b"", None
    while pos < len(raw):
        (length,) = struct.unpack(">I", raw[pos:pos + 4])
        kind = raw[pos + 4:pos + 8]
        payload = raw[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            idat += payload
        pos += length + 12

    assert header is not None, f"{path} has no IHDR"
    width, height, depth, colour, _, _, interlace = header
    assert (depth, colour, interlace) == (8, 6, 0), (
        f"{path} is not an 8-bit non-interlaced RGBA PNG: {header}"
    )

    data = zlib.decompress(idat)
    stride = width * 4
    out: list[tuple[int, int, int, int]] = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        filter_type = data[pos]
        line = bytearray(data[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for i in range(stride):
            left = line[i - 4] if i >= 4 else 0
            up = prev[i]
            up_left = prev[i - 4] if i >= 4 else 0
            if filter_type == 1:
                line[i] = (line[i] + left) & 0xFF
            elif filter_type == 2:
                line[i] = (line[i] + up) & 0xFF
            elif filter_type == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif filter_type == 4:
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                best = left if (pa <= pb and pa <= pc) else (up if pb <= pc else up_left)
                line[i] = (line[i] + best) & 0xFF
            elif filter_type != 0:
                raise AssertionError(f"{path}: unsupported PNG filter {filter_type}")
        out.extend(
            (line[i], line[i + 1], line[i + 2], line[i + 3])
            for i in range(0, stride, 4)
        )
        prev = line
    return width, height, out


def _png_dimensions(raw: bytes) -> tuple[int, int]:
    """(width, height) straight out of the IHDR, without decoding the pixels.

    Used to check the containers' own bookkeeping — an ICO directory entry or
    an ICNS chunk type against the frame it actually holds — where inflating a
    1024 px frame in pure Python would cost seconds for no extra assurance.
    """
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG payload"
    assert raw[12:16] == b"IHDR", "first chunk is not IHDR"
    return struct.unpack(">II", raw[16:24])


def _distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _letterform_runs(columns: dict[int, int]) -> list[int]:
    """Lettering pixel counts per run of consecutive ``x - y`` buckets."""
    if not columns:
        return []
    runs, current = [], [min(columns)]
    for key in sorted(columns)[1:]:
        if key == current[-1] + 1:
            current.append(key)
        else:
            runs.append(current)
            current = [key]
    runs.append(current)
    return [sum(columns[k] for k in run) for run in runs]


# ---------------------------------------------------------------------------
# Minimal ICO reader.
# ---------------------------------------------------------------------------
def _read_ico(path: Path) -> list[tuple[int, int, bytes]]:
    """Return [(width, height, payload)] for each frame in an ICO."""
    raw = path.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", raw[:6])
    assert (reserved, kind) == (0, 1), f"{path} is not an ICO"
    assert count > 0, f"{path} declares no frames"
    frames = []
    for i in range(count):
        entry = raw[6 + i * 16:6 + (i + 1) * 16]
        width, height = entry[0] or 256, entry[1] or 256
        size, offset = struct.unpack("<II", entry[8:16])
        assert offset + size <= len(raw), f"{path} frame {i} runs past end of file"
        frames.append((width, height, raw[offset:offset + size]))
    return frames


# ---------------------------------------------------------------------------
# Minimal ICNS reader.
# ---------------------------------------------------------------------------
# The pixel size each PNG-payload chunk type promises, per the ICNS format.
# The icon generator's ``write_icns`` picks the frame for each type off its own copy
# of this table; stating it independently here is what makes a transposed pair
# (ic07 handed the 256 px frame, say) a test failure rather than a shipped icon
# that macOS quietly rescales.
_ICNS_PNG_SIZES = {
    b"ic11": 32, b"ic12": 64, b"ic07": 128, b"ic13": 256,
    b"ic08": 256, b"ic14": 512, b"ic09": 512, b"ic10": 1024,
}


def _read_icns(path: Path) -> dict[bytes, bytes]:
    """Return {chunk type: payload} for an ICNS file."""
    raw = path.read_bytes()
    assert raw[:4] == b"icns", f"{path} is not an ICNS"
    assert struct.unpack(">I", raw[4:8])[0] == len(raw), f"{path}: wrong length field"
    chunks: dict[bytes, bytes] = {}
    pos = 8
    while pos < len(raw):
        kind = raw[pos:pos + 4]
        (length,) = struct.unpack(">I", raw[pos + 4:pos + 8])
        assert 8 < length <= len(raw) - pos, f"{path}: bad chunk length for {kind!r}"
        chunks[kind] = raw[pos + 8:pos + length]
        pos += length
    return chunks


def _unpack_icns_rle(data: bytes, expected: int) -> tuple[bytes, int]:
    """Decode one ARGB channel; returns (samples, bytes consumed).

    A control byte below 128 introduces ``n + 1`` literals, one at or above
    128 repeats the next byte ``n - 125`` times.
    """
    out = bytearray()
    pos = 0
    while len(out) < expected:
        assert pos < len(data), "ARGB channel ends before its pixel count"
        control = data[pos]
        pos += 1
        if control < 128:
            out += data[pos:pos + control + 1]
            pos += control + 1
        else:
            out += bytes([data[pos]]) * (control - 125)
            pos += 1
    assert len(out) == expected, f"ARGB channel overruns: {len(out)} != {expected}"
    return bytes(out), pos


def _icns_argb_last_op(payload: bytes, size: int) -> int:
    """The control byte of the final RLE op in an ``ic04``/``ic05`` payload.

    Below 128 it is a literal run, at or above it a repeat — and a repeat's
    value byte is the one byte a short reader drops. See the test below.
    """
    assert payload[:4] == b"ARGB", f"expected an ARGB payload, got {payload[:4]!r}"
    body, pos = payload[4:], 0
    for _ in range(3):                      # skip A, R and G
        _, used = _unpack_icns_rle(body[pos:], size * size)
        pos += used
    blue, control = body[pos:], None
    pos = 0
    while pos < len(blue):
        control = blue[pos]
        pos += 2 if control >= 128 else 2 + control
    assert control is not None, "the blue channel is empty"
    return control


def _decode_icns_argb(payload: bytes, size: int) -> list[tuple[int, int, int, int]]:
    """Decode an ``ic04``/``ic05`` payload to RGBA pixels."""
    assert payload[:4] == b"ARGB", f"expected an ARGB payload, got {payload[:4]!r}"
    body, pos, channels = payload[4:], 0, []
    for _ in range(4):
        channel, used = _unpack_icns_rle(body[pos:], size * size)
        channels.append(channel)
        pos += used
    assert pos == len(body), f"ARGB payload has {len(body) - pos} trailing bytes"
    alpha, red, green, blue = channels
    return [(red[i], green[i], blue[i], alpha[i]) for i in range(size * size)]


def _near(rgb, colour, tolerance: float) -> bool:
    return _distance(rgb[:3], colour) <= tolerance


def _badge_box(size: int) -> tuple[float, float, float, float]:
    """The DEMO pill's (x0, y0, x1, y1) on a ``size`` px square icon."""
    x1 = y1 = size * (1 - _BADGE_MARGIN)
    return x1 - size * _BADGE_W, y1 - size * _BADGE_H, x1, y1


def _in_box(x: int, y: int, box, pad: float = 0.0) -> bool:
    """Whether pixel (x, y), by its centre, falls inside ``box`` grown by ``pad``."""
    x0, y0, x1, y1 = box
    cx, cy = x + 0.5, y + 0.5
    return x0 - pad <= cx <= x1 + pad and y0 - pad <= cy <= y1 + pad


def _text_window(box, unit: float) -> tuple[float, float, float, float]:
    """The part of a pill's bounding box that is only pill or lettering.

    The rows of the cap height (88 of the badge's 150 units), and the columns
    24 units in from either end: at those rows the rounded ends have already
    reached 15 units in, and the lettering starts 44 in.  ``unit`` is the
    icon's side / 864.  Outside this window the bounding box holds the stage
    the pill's round ends leave uncovered, which is as dark as the ink.
    """
    x0, y0, x1, y1 = box
    mid = (y0 + y1) / 2
    return x0 + 24 * unit, mid - 44 * unit, x1 - 24 * unit, mid + 44 * unit


def _is_ink(rgba) -> bool:
    """Darker than the amber by a clear margin: the lettering, or its edge."""
    r, g, b = rgba[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b < 165


def _letterforms(ink_by_column: dict[int, int]) -> list[int]:
    """Ink pixel counts per run of consecutive columns: one run per letter."""
    return _letterform_runs({x: n for x, n in ink_by_column.items() if n})


class _Frame:
    """A decoded RGBA PNG icon frame, addressable by (x, y)."""

    def __init__(self, path: Path):
        self.path = path
        self.width, self.height, self.pixels = _read_png(path)

    @classmethod
    def from_bytes(cls, raw: bytes, label: str) -> "_Frame":
        frame = cls.__new__(cls)
        frame.path = label
        frame.width, frame.height, frame.pixels = _decode_png(raw, label)
        return frame

    def at(self, fx: float, fy: float) -> tuple[int, int, int, int]:
        """The pixel at a fraction of the frame's width and height."""
        x = min(self.width - 1, int(fx * self.width))
        y = min(self.height - 1, int(fy * self.height))
        return self.pixels[y * self.width + x]

    def __iter__(self):
        for index, rgba in enumerate(self.pixels):
            y, x = divmod(index, self.width)
            yield x, y, rgba


def _bundle_png(edition: str, name: str) -> Path:
    return _BUNDLE_DIR[edition] / name


_BUNDLE_PNGS = ("32x32.png", "128x128.png", "128x128@2x.png")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def base_icons() -> list[str]:
    return json.loads(_BASE_CONF.read_text())["bundle"]["icon"]


@pytest.fixture(scope="module")
def demo_icons() -> list[str]:
    return json.loads(_DEMO_CONF.read_text())["bundle"]["icon"]


# ---------------------------------------------------------------------------
# D-10a  The demo overlay actually overrides the icons
# ---------------------------------------------------------------------------
class TestDemoOverlayOverridesIcons:
    def test_demo_overlay_declares_bundle_icon(self, demo_icons):
        assert demo_icons, "tauri.demo.conf.json must override bundle.icon"

    def test_demo_covers_every_base_icon_file(self, base_icons, demo_icons):
        """Tauri replaces the array wholesale, so a short list drops a platform."""
        assert [Path(p).name for p in demo_icons] == [Path(p).name for p in base_icons]

    def test_demo_icons_live_outside_the_base_icon_directory(self, base_icons, demo_icons):
        base_dirs = {Path(p).parent for p in base_icons}
        demo_dirs = {Path(p).parent for p in demo_icons}
        assert demo_dirs.isdisjoint(base_dirs)

    def test_every_declared_icon_exists(self, base_icons, demo_icons):
        missing = [p for p in base_icons + demo_icons if not (_SRC_TAURI / p).is_file()]
        assert not missing, f"declared but absent: {missing}"

    def test_no_demo_icon_is_a_copy_of_the_base_icon(self, base_icons, demo_icons):
        """The regression itself: identical bytes meant identical icons in Steam."""
        base_by_name = {Path(p).name: _SRC_TAURI / p for p in base_icons}
        for rel in demo_icons:
            demo = _SRC_TAURI / rel
            base = base_by_name[demo.name]
            assert demo.read_bytes() != base.read_bytes(), (
                f"{demo.name} is byte-identical to the base app's"
            )


# ---------------------------------------------------------------------------
# D-10b  Both editions draw the official icon; the demo adds only the badge
# ---------------------------------------------------------------------------
class TestEveryFrameIsTheOfficialIcon:
    """The bundle frames are ConversationSimulatorIcon.svg, in the tile shape."""

    @pytest.mark.parametrize("edition", _EDITIONS)
    @pytest.mark.parametrize("name", _BUNDLE_PNGS)
    def test_the_two_voices(self, edition, name):
        """Violet below-left and emerald above-right, where the source has them."""
        frame = _Frame(_bundle_png(edition, name))
        assert _near(frame.at(*_YOU_AT), _YOU, 24), (
            f"{edition}/{name}: {frame.at(*_YOU_AT)} where the violet bubble should be"
        )
        assert _near(frame.at(*_THEM_AT), _THEM, 24), (
            f"{edition}/{name}: {frame.at(*_THEM_AT)} where the emerald bubble should be"
        )

    @pytest.mark.parametrize("edition", _EDITIONS)
    @pytest.mark.parametrize("name", _BUNDLE_PNGS)
    def test_the_dark_stage(self, edition, name):
        """Open stage between the bubbles and the corner is the source's grey gradient."""
        r, g, b, a = _Frame(_bundle_png(edition, name)).at(0.12, 0.12)
        assert a == 255
        assert max(r, g, b) - min(r, g, b) <= 3, f"{edition}/{name}: stage is not grey"
        assert _STAGE_DARK[0] - 3 <= r <= _STAGE_LIGHT[0] + 3, (
            f"{edition}/{name}: stage {r, g, b} is outside the icon's gradient"
        )

    @pytest.mark.parametrize("edition", _EDITIONS)
    @pytest.mark.parametrize("name", _BUNDLE_PNGS)
    def test_rounded_corners(self, edition, name):
        frame = _Frame(_bundle_png(edition, name))
        w, h = frame.width, frame.height
        for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            assert frame.pixels[y * w + x][3] == 0, f"{edition}/{name}: corner ({x}, {y}) is opaque"

    @pytest.mark.parametrize("edition", _EDITIONS)
    @pytest.mark.parametrize("name", _BUNDLE_PNGS)
    def test_no_retired_colour(self, edition, name):
        """No trace of the old teal or purple plates or the capsule-only green."""
        frame = _Frame(_bundle_png(edition, name))
        stray = [(x, y) for x, y, rgba in frame
                 if rgba[3] > 200 and any(_near(rgba, c, 20) for c in _RETIRED)]
        assert not stray, f"{edition}/{name}: retired brand colour at {stray[:5]}"

    @pytest.mark.parametrize("name", _BUNDLE_PNGS)
    def test_png_dimensions(self, name):
        expected = {"32x32.png": 32, "128x128.png": 128, "128x128@2x.png": 256}[name]
        for edition in _EDITIONS:
            frame = _Frame(_bundle_png(edition, name))
            assert (frame.width, frame.height) == (expected, expected)


class TestDemoIsTheIconWithABadge:
    """Demo = base + badge, and nothing else: the demo must read as the same product."""

    @pytest.mark.parametrize("name", _BUNDLE_PNGS)
    def test_identical_to_the_base_outside_the_badge(self, name):
        base = _Frame(_bundle_png("base", name))
        demo = _Frame(_bundle_png("demo", name))
        box = _badge_box(base.width)
        moved = [
            (x, y) for (x, y, b), (_, _, d) in zip(base, demo)
            if not _in_box(x, y, box, pad=1.0) and max(abs(i - j) for i, j in zip(b, d)) > 2
        ]
        assert not moved, f"{name}: the demo differs from the base outside the badge at {moved[:5]}"

    @pytest.mark.parametrize("name", _BUNDLE_PNGS)
    def test_the_badge_is_amber(self, name):
        """At every size, 32 px included: the pill's colour is the cue that survives.

        Measured over the pill's bounding box, which its round ends and its
        lettering share: at 32 px about a third of it is still clean amber.
        """
        demo = _Frame(_bundle_png("demo", name))
        box = _badge_box(demo.width)
        inside = [rgba for x, y, rgba in demo if _in_box(x, y, box)]
        amber = sum(1 for rgba in inside if _near(rgba, _BADGE, 40))
        assert inside and amber >= 0.3 * len(inside), (
            f"{name}: only {amber}/{len(inside)} badge pixels are amber"
        )

    @pytest.mark.parametrize("name", _BUNDLE_PNGS)
    def test_the_base_has_no_badge(self, name):
        base = _Frame(_bundle_png("base", name))
        amber = sum(1 for _, _, rgba in base if rgba[3] > 200 and _near(rgba, _BADGE, 40))
        assert amber == 0, f"{name}: the full game's icon carries {amber} amber pixels"

    @pytest.mark.parametrize("name", ("128x128.png", "128x128@2x.png"))
    def test_the_badge_spells_four_letters(self, name):
        """Dark lettering in the pill, in four separate runs of columns: D, E, M, O."""
        demo = _Frame(_bundle_png("demo", name))
        window = _text_window(_badge_box(demo.width), demo.width / 864)
        columns: dict[int, int] = {}
        inside = ink = 0
        for x, y, rgba in demo:
            if not _in_box(x, y, window):
                continue
            inside += 1
            if _is_ink(rgba):
                ink += 1
                columns[x] = columns.get(x, 0) + 1
            else:
                assert _near(rgba, _BADGE, 60), f"{name}: {rgba} at ({x}, {y}) is neither pill nor ink"
        assert 0.15 <= ink / inside <= 0.6, f"{name}: lettering is {ink}/{inside} of the pill"
        runs = _letterforms(columns)
        assert len(runs) == 4, f"{name}: {len(runs)} letterform(s), not four: {runs}"


# ---------------------------------------------------------------------------
# D-10c  The ICO and ICNS containers
# ---------------------------------------------------------------------------
_ICNS_REQUIRED = {b"ic04", b"ic05", b"ic07", b"ic08", b"ic09", b"ic10",
                  b"ic11", b"ic12", b"ic13", b"ic14"}


class TestIconContainers:
    @pytest.mark.parametrize("edition", _EDITIONS)
    def test_ico_carries_the_sizes_windows_asks_for(self, edition):
        sizes = {w for w, _, _ in _read_ico(_BUNDLE_DIR[edition] / "icon.ico")}
        assert {16, 24, 32, 48, 64, 128, 256} <= sizes, f"{edition} icon.ico is missing sizes: {sizes}"

    @pytest.mark.parametrize("edition", _EDITIONS)
    def test_ico_entries_match_the_frames_they_point_at(self, edition):
        """A directory entry that lies about its frame's size makes Windows rescale."""
        for width, height, payload in _read_ico(_BUNDLE_DIR[edition] / "icon.ico"):
            assert _png_dimensions(payload) == (width, height), (
                f"{edition} icon.ico declares a {width}x{height} frame but holds "
                f"{_png_dimensions(payload)}"
            )

    @pytest.mark.parametrize("edition", _EDITIONS)
    @pytest.mark.parametrize("size,name", ((32, "32x32.png"), (128, "128x128.png"),
                                           (256, "128x128@2x.png")))
    def test_ico_frames_are_the_bundle_pngs(self, edition, size, name):
        ico = {w: payload for w, _, payload in _read_ico(_BUNDLE_DIR[edition] / "icon.ico")}
        assert ico[size] == _bundle_png(edition, name).read_bytes(), (
            f"{edition} icon.ico's {size} px frame is not {name}"
        )

    @pytest.mark.parametrize("edition", _EDITIONS)
    def test_icns_is_well_formed_and_complete(self, edition):
        chunks = _read_icns(_BUNDLE_DIR[edition] / "icon.icns")
        missing = _ICNS_REQUIRED - set(chunks)
        assert not missing, f"{edition} icon.icns is missing representations: {missing}"
        for kind, payload in chunks.items():
            if kind in _ICNS_PNG_SIZES:
                size = _ICNS_PNG_SIZES[kind]
                assert _png_dimensions(payload) == (size, size), (
                    f"{edition} icon.icns {kind!r} promises {size} px"
                )

    @pytest.mark.parametrize("edition", _EDITIONS)
    def test_icns_sits_on_apples_icon_grid(self, edition):
        """824/1024 of the canvas, centred: a transparent 100/1024 margin all round.

        A full-bleed square sits oversized in the Dock, and macOS 26 sets an
        icon that does not fill the standard shape on a grey plate of its own.
        """
        chunks = _read_icns(_BUNDLE_DIR[edition] / "icon.icns")
        frame = _Frame.from_bytes(chunks[b"ic07"], f"{edition} icns ic07")   # 128 px
        margin = 128 * 100 / 1024                                            # 12.5 px
        assert frame.pixels[64 * 128 + int(margin) - 2][3] == 0, "no left margin"
        assert frame.pixels[64 * 128 + int(margin) + 2][3] == 255, "art does not start at the grid"
        assert frame.pixels[(int(margin) - 2) * 128 + 64][3] == 0, "no top margin"
        corner = int(margin) + 2
        assert frame.pixels[corner * 128 + corner][3] == 0, "the art's corner is not rounded"
        assert _near(frame.at(0.5 + (_THEM_AT[0] - 0.5) * 824 / 1024,
                              0.5 + (_THEM_AT[1] - 0.5) * 824 / 1024), _THEM, 24)

    @pytest.mark.parametrize("edition", _EDITIONS)
    def test_icns_argb_32_matches_its_png_twin(self, edition):
        """ic05 (32 px ARGB) and ic11 (32 px PNG) are the same frame."""
        chunks = _read_icns(_BUNDLE_DIR[edition] / "icon.icns")
        argb = _decode_icns_argb(chunks[b"ic05"], 32)
        _, _, png = _decode_png(chunks[b"ic11"], f"{edition} icns ic11")
        assert argb == png, f"{edition} icon.icns: ic05 does not decode to ic11's frame"

    @pytest.mark.parametrize("edition", _EDITIONS)
    def test_icns_argb_16_decodes(self, edition):
        chunks = _read_icns(_BUNDLE_DIR[edition] / "icon.icns")
        pixels = _decode_icns_argb(chunks[b"ic04"], 16)
        assert pixels[0][3] == 0, "the 16 px frame's corner is not transparent"
        assert pixels[8 * 16 + 8][3] == 255, "the 16 px frame's centre is not opaque"

    @pytest.mark.parametrize("edition", _EDITIONS)
    @pytest.mark.parametrize("kind,size", ((b"ic04", 16), (b"ic05", 32)))
    def test_icns_argb_payload_ends_on_a_literal(self, edition, kind, size):
        """``iconutil`` reads one byte short of an ARGB payload; a trailing
        repeat would lose its value byte and up to 130 blue samples with it."""
        chunks = _read_icns(_BUNDLE_DIR[edition] / "icon.icns")
        assert _icns_argb_last_op(chunks[kind], size) < 128, (
            f"{edition} icon.icns {kind!r}: the blue channel ends on a run"
        )

