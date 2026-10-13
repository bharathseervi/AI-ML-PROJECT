"""Read-aloud button using the browser's own speech synthesis (Web Speech API). Nothing is sent to a server.

Whether it works depends on the visitor's device: a voice for the language (en-IN, kn-IN, hi-IN) must be installed,
and Kannada voices in particular are missing on many systems. The button says so.
"""
import json

LANG_CODES = {"en": "en-IN", "kn": "kn-IN", "hi": "hi-IN"}


def _js_string(text: str) -> str:
    """A JSON string that is safe to place inside a <script> block."""
    s = json.dumps(text, ensure_ascii=True)       # non-ASCII becomes \\uXXXX, so no raw line separators either
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def speech_html(lines: list[str], lang: str, label: str, note: str) -> str:
    """HTML for st.components.v1.html. `lines` are spoken one after another (long text is cut into pieces because some
    browsers stop a single long utterance after about 15 seconds)."""
    code = LANG_CODES.get(lang, "en-IN")
    return f"""
<div style="font-family:sans-serif">
  <button id="rd" style="width:100%;min-height:52px;font-size:18px;font-weight:600;border-radius:8px;border:1px solid #888;background:#fff;cursor:pointer">
    &#128266; {label.replace("<", "&lt;")}
  </button>
  <div id="msg" style="font-size:12px;color:#666;margin-top:4px">{note.replace("<", "&lt;")}</div>
</div>
<script>
  const LINES = {_js_string(json.dumps(lines, ensure_ascii=False))};
  const LANG = {_js_string(code)};
  const btn = document.getElementById("rd");
  btn.onclick = () => {{
    if (!("speechSynthesis" in window)) {{ document.getElementById("msg").textContent = "This browser cannot read aloud."; return; }}
    if (speechSynthesis.speaking) {{ speechSynthesis.cancel(); return; }}      // second click stops
    JSON.parse(LINES).forEach(line => {{
      const u = new SpeechSynthesisUtterance(line);
      u.lang = LANG;
      const v = speechSynthesis.getVoices().find(x => x.lang && x.lang.toLowerCase().startsWith(LANG.slice(0, 2).toLowerCase()));
      if (v) u.voice = v;
      speechSynthesis.speak(u);
    }});
  }};
</script>
"""
