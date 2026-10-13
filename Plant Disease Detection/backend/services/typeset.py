"""Text drawing for the PDF report, including correct Kannada and Hindi.

Why this exists: ReportLab draws text one Unicode character at a time and does no "shaping". Kannada and
Devanagari need shaping (conjunct consonants, vowel signs that move before the consonant, split vowels), so
plain ReportLab output looks broken. Here we
  1. shape each run of text with HarfBuzz (uharfbuzz), which returns the correct glyphs and positions,
  2. take each glyph's outline from the font with fontTools,
  3. draw the outlines as vector paths on the PDF page.
The result is pixel-perfect and sharp at any zoom, but the Kannada/Hindi text in the PDF is not selectable or
searchable (English uses normal PDF text and is). Fonts: Noto Sans, Noto Sans Kannada, Noto Sans Devanagari
(SIL Open Font License, see backend/assets/fonts/OFL.txt), default Regular weight; "bold" is simulated.
"""
from pathlib import Path

from reportlab.pdfbase.pdfmetrics import stringWidth

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT_FILES = {"latin": "NotoSans.ttf", "kn": "NotoSansKannada.ttf", "hi": "NotoSansDevanagari.ttf"}


def font_key(ch: str):
    """'kn' / 'hi' / 'latin' for a character that clearly belongs to one font, or None if it is neutral
    (space, punctuation, joiners) and should stay with the surrounding run."""
    o = ord(ch)
    if 0x0C80 <= o <= 0x0CFF:
        return "kn"
    if 0x0900 <= o <= 0x097F or 0xA8E0 <= o <= 0xA8FF:
        return "hi"
    if ch.isalnum() or ch in "°×–—’‘“”":
        return "latin"
    return None


def split_runs(text: str) -> list[tuple[str, str]]:
    """Split text into (font_key, substring) runs. Neutral characters join the current run."""
    runs: list[list] = []
    current = None
    for ch in text:
        k = font_key(ch) or current or "latin"
        if runs and runs[-1][0] == k:
            runs[-1][1] += ch
        else:
            runs.append([k, ch])
        current = k
    return [(k, s) for k, s in runs]


class _Face:
    """One font file loaded for shaping (HarfBuzz) and for outlines (fontTools)."""

    def __init__(self, path: Path):
        import uharfbuzz as hb
        from fontTools.ttLib import TTFont

        self._hb = hb
        self.hb_font = hb.Font(hb.Face(hb.Blob(path.read_bytes())))
        tt = TTFont(path)
        self.glyph_set = tt.getGlyphSet()
        self.order = tt.getGlyphOrder()
        self.upem = tt["head"].unitsPerEm
        self._paths = {}

    def shape(self, text: str):
        buf = self._hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()  # detects script and direction from the text
        self._hb.shape(self.hb_font, buf, {"kern": True, "liga": True})
        return [(i.codepoint, p.x_advance, p.x_offset, p.y_offset) for i, p in zip(buf.glyph_infos, buf.glyph_positions)]

    def outline(self, gid: int) -> list:
        """Glyph outline as a list of ("m"|"l"|"c"|"z", *coords) operations, in font units."""
        if gid not in self._paths:
            from fontTools.pens.basePen import BasePen

            class Rec(BasePen):  # BasePen turns TrueType quadratic curves into cubic ones for us
                def __init__(self, glyph_set):
                    super().__init__(glyph_set)
                    self.ops = []

                def _moveTo(self, pt):
                    self.ops.append(("m", *pt))

                def _lineTo(self, pt):
                    self.ops.append(("l", *pt))

                def _curveToOne(self, p1, p2, p3):
                    self.ops.append(("c", *p1, *p2, *p3))

                def _closePath(self):
                    self.ops.append(("z",))

            pen = Rec(self.glyph_set)
            self.glyph_set[self.order[gid]].draw(pen)
            self._paths[gid] = pen.ops
        return self._paths[gid]


_faces: dict[str, _Face] = {}


def face(key: str) -> _Face:
    if key not in _faces:
        _faces[key] = _Face(FONT_DIR / FONT_FILES[key])
    return _faces[key]


class ShapedTypesetter:
    """Kannada / Hindi (and Latin words inside them) via HarfBuzz + vector outlines."""

    def __init__(self):
        self._cache: dict[tuple, list] = {}

    def _shaped(self, text: str):
        if text not in self._cache:
            out = []
            for key, run in split_runs(text):
                f = face(key)
                out.append((f, f.shape(run)))
            self._cache[text] = out
        return self._cache[text]

    def width(self, text: str, size: float, bold: bool = False) -> float:
        total = sum(adv * size / f.upem for f, glyphs in self._shaped(text) for _, adv, _, _ in glyphs)
        return total + (0.02 * size * len(text) if bold else 0)

    @staticmethod
    def _glyph_form(c, f: "_Face", gid: int, bold: bool) -> str:
        """Define each glyph once per PDF as a reusable form, so a page of text does not repeat every outline."""
        forms = c.__dict__.setdefault("_glyph_forms", {})
        key = (id(f), gid, bold)
        if key not in forms:
            name = f"glyph{len(forms)}"
            span = 4 * f.upem  # generous bounding box in font units so no glyph is clipped
            c.beginForm(name, -span, -span, span, span)
            path = c.beginPath()
            for op, *pts in f.outline(gid):
                if op == "m":
                    path.moveTo(*pts)
                elif op == "l":
                    path.lineTo(*pts)
                elif op == "c":
                    path.curveTo(*pts)
                else:
                    path.close()
            if bold:  # faux bold: fill plus a thin outline in the current colour
                c.setLineWidth(f.upem * 0.025)
            c.drawPath(path, stroke=1 if bold else 0, fill=1)
            c.endForm()
            forms[key] = name
        return forms[key]

    def draw(self, c, x: float, y: float, text: str, size: float, color=(0, 0, 0), bold: bool = False):
        c.setFillColorRGB(*color)
        c.setStrokeColorRGB(*color)
        for f, glyphs in self._shaped(text):
            scale = size / f.upem
            for gid, adv, xo, yo in glyphs:
                form = self._glyph_form(c, f, gid, bold)
                c.saveState()
                c.translate(x + xo * scale, y + yo * scale)
                c.scale(scale, scale)
                c.doForm(form)
                c.restoreState()
                x += adv * scale
        return x


class NativeTypesetter:
    """English: normal, selectable PDF text in Helvetica."""

    def width(self, text: str, size: float, bold: bool = False) -> float:
        return stringWidth(text, "Helvetica-Bold" if bold else "Helvetica", size)

    def draw(self, c, x, y, text, size, color=(0, 0, 0), bold=False):
        c.setFillColorRGB(*color)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, y, text)
        return x + self.width(text, size, bold)


def typesetter_for(lang: str):
    return NativeTypesetter() if lang == "en" else ShapedTypesetter()


def wrap(ts, text: str, size: float, max_width: float, bold: bool = False) -> list[str]:
    """Greedy word wrap using the typesetter's own widths. Over-long words (URLs) are broken by character."""
    lines, line = [], ""
    for word in text.split(" "):
        trial = word if not line else line + " " + word
        if ts.width(trial, size, bold) <= max_width:
            line = trial
            continue
        if line:
            lines.append(line)
        line = ""
        while ts.width(word, size, bold) > max_width and len(word) > 1:  # hard-break a token that never fits
            cut = len(word)
            while cut > 1 and ts.width(word[:cut], size, bold) > max_width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        line = word
    if line:
        lines.append(line)
    return lines or [""]
