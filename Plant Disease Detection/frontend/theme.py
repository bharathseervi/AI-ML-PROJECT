"""Visual theme: the rice photo as page background, glass-style cards, rounded controls, light and dark variants.

css(dark) returns one <style> block. The photo is served by Streamlit's static file server (frontend/static/,
enabled in .streamlit/config.toml), so it is not sent again on every interaction.
"""

BACKGROUND_URL = "/app/static/background.jpg"
CARD = '[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]'

_TOKENS = {
    False: {
        "overlay": "linear-gradient(180deg, rgba(6,22,12,.52) 0%, rgba(6,22,12,.32) 40%, rgba(6,22,12,.66) 100%)",
        "card": "rgba(255,255,255,.88)", "card_solid": "#ffffff", "field": "rgba(255,255,255,.96)",
        "text": "#1b2a1f", "muted": "#586a5d", "border": "rgba(255,255,255,.7)", "line": "rgba(31,122,61,.18)",
        "soft": "rgba(31,122,61,.08)", "shadow": "0 18px 48px rgba(0,0,0,.30)",
    },
    True: {
        "overlay": "linear-gradient(180deg, rgba(2,10,6,.78) 0%, rgba(2,10,6,.66) 45%, rgba(2,10,6,.86) 100%)",
        "card": "rgba(17,27,20,.88)", "card_solid": "#131f17", "field": "rgba(28,41,32,.96)",
        "text": "#edf5ee", "muted": "#a6b9ab", "border": "rgba(255,255,255,.13)", "line": "rgba(255,255,255,.14)",
        "soft": "rgba(255,255,255,.06)", "shadow": "0 18px 48px rgba(0,0,0,.55)",
    },
}

_TEMPLATE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --card: __card__; --card-solid: __card_solid__; --field: __field__;
  --text: __text__; --muted: __muted__; --border: __border__; --line: __line__; --soft: __soft__;
  --shadow: __shadow__;
  --accent: #1f7a3d; --accent-2: #2e9e4f; --gold: #e8a317;
}

/* ---- page ---------------------------------------------------------------------------------- */
.stApp {
  background: __overlay__, url(__bg__) center / cover fixed no-repeat, #16301f;
  font-family: 'Inter', 'Noto Sans', 'Noto Sans Kannada', 'Noto Sans Devanagari', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
[data-testid="stHeader"] { display: none !important; }   /* an invisible bar that would otherwise sit over the controls and swallow clicks */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton { display: none !important; }
.block-container { max-width: 820px; padding: 1.2rem 1rem 4rem; }

/* ---- hero (sits on the photo, so white text) -------------------------------------------------- */
.stApp h1 {
  color: #fff !important; font-weight: 800; letter-spacing: -.02em; line-height: 1.12;
  font-size: clamp(2rem, 6vw, 3.1rem); text-shadow: 0 2px 22px rgba(0,0,0,.55); padding: .6rem 0 .2rem;
}
.hero-sub { color: rgba(255,255,255,.93); font-size: clamp(1rem, 2.4vw, 1.18rem); line-height: 1.5; max-width: 640px;
  text-shadow: 0 1px 12px rgba(0,0,0,.55); margin: 0 0 .9rem; }
.chips { display: flex; flex-wrap: wrap; gap: .45rem; margin: .2rem 0 1rem; }
.chip { display: inline-flex; align-items: center; gap: .4rem; padding: .32rem .8rem; border-radius: 999px; font-size: .82rem; font-weight: 600;
  color: #fff; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.34); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); }
.chip.ok::before, .chip.bad::before { content: ""; width: .55rem; height: .55rem; border-radius: 50%; background: #4ade80; box-shadow: 0 0 0 3px rgba(74,222,128,.28); }
.chip.bad::before { background: #f87171; box-shadow: 0 0 0 3px rgba(248,113,113,.3); }
.note { color: rgba(255,255,255,.95); font-size: .88rem; line-height: 1.5; padding: .8rem 1rem; border-radius: 16px; margin: 0 0 1.1rem;
  background: rgba(0,0,0,.34); border: 1px solid rgba(255,255,255,.22); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); }

/* ---- cards ---------------------------------------------------------------------------------- */
__CARD__ {
  background: var(--card); border: 1px solid var(--border) !important; border-radius: 24px !important;
  box-shadow: var(--shadow); backdrop-filter: blur(18px) saturate(1.15); -webkit-backdrop-filter: blur(18px) saturate(1.15);
  padding: 1.2rem 1.3rem; margin-bottom: 1.2rem; animation: rise .45s ease both;
}
@keyframes rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }

/* text colours inside cards (works in light and dark) */
__CARD__ p, __CARD__ li, __CARD__ label,
__CARD__ h1, __CARD__ h2, __CARD__ h3,
__CARD__ h4, __CARD__ summary, __CARD__ summary span,
__CARD__ [data-testid="stMetricValue"], __CARD__ [data-testid="stMetricLabel"],
__CARD__ td, __CARD__ th, __CARD__ strong { color: var(--text) !important; }
__CARD__ [data-testid="stCaptionContainer"], __CARD__ [data-testid="stCaptionContainer"] p { color: var(--muted) !important; }
__CARD__ a { color: var(--accent-2) !important; }
__CARD__ h3 { font-weight: 800; letter-spacing: -.01em; font-size: 1.7rem; }
[data-testid="stMetricValue"] { font-weight: 800; }
__CARD__ table { border-collapse: separate; border-spacing: 0; width: 100%; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; font-size: .92rem; }
__CARD__ th { background: var(--soft); font-weight: 700; }
__CARD__ td, __CARD__ th { border: 0; border-bottom: 1px solid var(--line); padding: .55rem .7rem; }

/* ---- controls ----------------------------------------------------------------------------------- */
[data-baseweb="select"] > div { background: var(--field) !important; border-radius: 999px !important; border: 1px solid var(--border) !important; min-height: 3rem; box-shadow: 0 6px 22px rgba(0,0,0,.18); }
[data-baseweb="select"] * { color: var(--text) !important; }
[data-baseweb="popover"] ul, [data-baseweb="menu"] { background: var(--card-solid) !important; }
[data-baseweb="popover"] li { color: var(--text) !important; }

.stButton > button, [data-testid="stDownloadButton"] > button {
  min-height: 3.3rem; font-size: 1.05rem; font-weight: 700; border-radius: 16px; border: 1px solid var(--line);
  background: var(--field); color: var(--text) !important; transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.stButton > button:hover, [data-testid="stDownloadButton"] > button:hover { transform: translateY(-2px); border-color: var(--accent-2); box-shadow: 0 10px 24px rgba(31,122,61,.25); }
.stButton > button:active, [data-testid="stDownloadButton"] > button:active { transform: translateY(0) scale(.99); }
.stButton > button[kind="primary"], [data-testid="stDownloadButton"] > button[kind="primary"] {
  background: linear-gradient(135deg, #2e9e4f 0%, #1f7a3d 55%, #176030 100%); color: #fff !important; border: 0; letter-spacing: .01em; box-shadow: 0 10px 26px rgba(31,122,61,.45);
}
.stButton > button[kind="primary"] *, [data-testid="stDownloadButton"] > button[kind="primary"] * { color: #fff !important; }

[data-testid="stFileUploaderDropzone"] { border: 2px dashed var(--accent-2); border-radius: 20px; background: var(--soft); padding: 1.3rem; }
[data-testid="stFileUploaderDropzone"] * { color: var(--text) !important; }
[data-testid="stFileUploaderDropzone"] button { border-radius: 12px; background: var(--field) !important; border: 1px solid var(--line) !important; }
[data-testid="stFileUploaderDropzone"] button * { color: var(--text) !important; }
[data-testid="stFileUploaderFile"] small, [data-testid="stFileUploaderFileData"] small { color: var(--muted) !important; }
[data-testid="stFileUploaderFileName"] { color: var(--text) !important; }
[data-testid="stCameraInput"] { border-radius: 20px; overflow: hidden; }
[data-testid="stRadio"] [role="radiogroup"] { gap: .6rem; }
[data-testid="stRadio"] [role="radiogroup"] label { background: var(--soft); border: 1px solid var(--line); border-radius: 999px; padding: .35rem 1rem; }
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) { background: var(--accent); border-color: var(--accent); }
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) * { color: #fff !important; }
[data-testid="stToggle"] *:not(input) { color: #fff !important; text-shadow: 0 1px 8px rgba(0,0,0,.55); font-weight: 600; }

[data-testid="stExpander"] { background: var(--soft); border: 1px solid var(--line) !important; border-radius: 18px !important; margin: .35rem 0; overflow: hidden; }
[data-testid="stExpander"] summary { padding: .75rem 1rem; font-weight: 700; }
[data-testid="stExpander"] summary:hover { background: var(--soft); }

[data-testid="stAlert"] { border-radius: 16px; border: 1px solid var(--line); }
/* progress bar: outer wrapper -> wrapper -> track -> fill (checked in the browser DOM) */
[data-testid="stProgress"] [role="progressbar"], [data-testid="stProgress"] [role="progressbar"] > div { background: transparent !important; }
[data-testid="stProgress"] [role="progressbar"] > div > div { background: var(--soft) !important; border-radius: 999px; height: .55rem; }
[data-testid="stProgress"] [role="progressbar"] > div > div > div { background: linear-gradient(90deg, var(--accent-2), var(--gold)) !important; border-radius: 999px; }
[data-testid="stImage"] img { border-radius: 18px; box-shadow: 0 10px 30px rgba(0,0,0,.28); }
hr { border-color: var(--line) !important; }
[data-testid="stSpinner"] * { color: var(--text) !important; }

/* ---- small screens ------------------------------------------------------------------------------- */
@media (max-width: 640px) {
  .block-container { padding: .8rem .6rem 3rem; }
  __CARD__ { padding: .9rem .85rem; border-radius: 20px !important; }
  .stButton > button { min-height: 3.5rem; }
}
</style>
"""


def css(dark: bool = False, background_url: str = BACKGROUND_URL) -> str:
    # The cards are the bordered containers that are direct children of the page's vertical block. The page root,
    # the columns and the expander bodies use the same wrapper element, so a plain wrapper selector would style them too.
    out = _TEMPLATE.replace("__CARD__", CARD).replace("__bg__", background_url)
    for key, value in _TOKENS[bool(dark)].items():
        out = out.replace(f"__{key}__", value)
    return out
