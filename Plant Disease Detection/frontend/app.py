"""Streamlit frontend. Run from the project root:

    streamlit run frontend/app.py

It talks to the Flask backend over HTTP (API_URL env var, default http://127.0.0.1:5000).
The look (photo background, glass cards, light/dark) is in theme.py; the photo is frontend/static/background.jpg.
"""
import base64
import html
import uuid
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import api_client
import session_tools
import speech
import theme
from i18n import LANGUAGES, t

st.set_page_config(page_title="Rice Leaf Disease Detector", page_icon="🌾", layout="centered", initial_sidebar_state="collapsed")

# Session state: history of this browser session and the latest outcome shown below the button.
st.session_state.setdefault("history", [])
st.session_state.setdefault("last", None)

# ---- Top bar: language and dark mode ------------------------------------------
bar = st.columns([3, 2])
with bar[0]:
    lang_name = st.selectbox("Language / ಭಾಷೆ / भाषा", list(LANGUAGES), label_visibility="collapsed")
lang = LANGUAGES[lang_name]
with bar[1]:
    dark = st.toggle(t(lang, "dark_mode"), key="dark")
st.markdown(theme.css(dark), unsafe_allow_html=True)

# ---- Hero ---------------------------------------------------------------------
health = api_client.health()
status_chip = (f'<span class="chip ok">{html.escape(t(lang, "backend_ok"))}</span>' if health is not None
               else f'<span class="chip bad">{html.escape(t(lang, "backend_down"))}</span>')
feature_chips = "".join(f'<span class="chip">{html.escape(c)}</span>' for c in t(lang, "chips"))
st.title(t(lang, "title"))
st.markdown(
    f'<div class="hero-sub">{html.escape(t(lang, "subtitle"))}</div>'
    f'<div class="chips">{status_chip}{feature_chips}</div>'
    f'<div class="note">{html.escape(t(lang, "disclaimer"))}</div>',
    unsafe_allow_html=True,
)

def run_diagnosis(data: bytes, name: str) -> dict:
    """Single entry point for both inputs. Returns a dict describing the outcome."""
    try:
        return {"kind": "ok", "result": api_client.predict(data, name)}
    except api_client.BackendDown:
        return {"kind": "backend_down"}
    except api_client.ModelNotReady as exc:
        return {"kind": "model_not_ready", "reason": exc.reason, "quality": exc.quality}
    except api_client.BadImage as exc:
        return {"kind": "bad_image", "message": str(exc)}
    except api_client.BackendError:
        return {"kind": "error"}


# ---- Input card: tips, upload or camera, one shared pipeline -------------------
with st.container(border=True):
    with st.expander(t(lang, "tips_title"), expanded=False):
        for tip in t(lang, "tips"):
            st.markdown(f"- {tip}")
    mode = st.radio(
        t(lang, "input_mode"),
        [t(lang, "mode_upload"), t(lang, "mode_camera")],
        horizontal=True,
    )
    if mode == t(lang, "mode_upload"):
        picked = st.file_uploader(t(lang, "upload_label"), type=["jpg", "jpeg", "png"])
        filename = picked.name if picked else None
    else:
        picked = st.camera_input(t(lang, "camera_label"))  # needs HTTPS or localhost
        filename = "camera.jpg" if picked else None

    image_bytes = picked.getvalue() if picked else None
    if image_bytes:
        st.image(image_bytes, use_column_width=True)

    if st.button(t(lang, "diagnose"), type="primary", use_container_width=True):
        if not image_bytes:
            st.session_state.last = {"kind": "no_image"}
        else:
            with st.spinner(t(lang, "analysing")):
                outcome = run_diagnosis(image_bytes, filename)
            outcome.update(id=uuid.uuid4().hex, image_bytes=image_bytes, filename=filename)  # kept for the PDF report
            st.session_state.last = outcome
            st.session_state.pdf = None
            if outcome["kind"] == "ok":
                r = outcome["result"]
                sev = r.get("severity") or {}
                st.session_state.history.append(
                    {
                        "id": outcome["id"],
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        # the English label is stored and translated when the table is drawn, so a language switch updates it
                        "disease": "—" if r.get("rejected") else r.get("label", "—"),
                        "confidence": f"{r.get('confidence', 0) * 100:.1f}%",
                        # the English level is stored and translated when shown, like the disease name
                        "severity": sev["level"] if sev.get("leaf_found") and sev.get("level") else "—",
                    }
                )

# ---- Result -----------------------------------------------------------------
def show_quality(q):
    """Photo-quality warnings from the backend (blurry / too dark / overexposed)."""
    for issue in (q or {}).get("issues", []):
        st.warning(t(lang, f"quality_{issue}"))


def show_severity(r):
    sev = r.get("severity")
    if sev and sev.get("leaf_found"):
        st.metric(t(lang, f"sev_{sev['level']}"), f"{sev['percent']:.1f}%")
        st.caption(t(lang, "severity_of_leaf"))
        if sev.get("overlay_png_b64"):
            st.image(base64.b64decode(sev["overlay_png_b64"]), use_column_width=True)
        st.caption(t(lang, "severity_limits"))
    elif sev:  # leaf not found in the photo
        st.info(t(lang, "severity_no_leaf"))
    elif r.get("label") == "Healthy":
        st.caption(t(lang, "severity_healthy"))
    elif r.get("rejected"):
        st.caption(t(lang, "severity_rejected"))
    else:
        st.caption(t(lang, "coming_soon"))


disease_names = api_client.names(lang)  # {"Blast": "ಬ್ಲಾಸ್ಟ್ ರೋಗ (Blast)", ...}; empty if the backend is down


def disp(label):
    return disease_names.get(label, label)


def sev_text(level):
    return t(lang, f"sev_{level}") if level in session_tools.LEVELS else "—"


def hist_text(row):
    """'Blast, Mild' or 'Not diagnosed' in the current language."""
    if row["disease"] == "—":
        return t(lang, "not_diagnosed")
    sev = row.get("severity")
    return disp(row["disease"]) + (f", {sev_text(sev)}" if sev in session_tools.LEVELS else "")


def bullets(items):
    for item in items:
        st.markdown(f"- {item}")


def show_advice(r):
    """Knowledge-base advice (symptoms, causes, treatment, growth) for the diagnosed disease."""
    sev = r.get("severity") or {}
    info = api_client.info(r["label"], lang, sev.get("level") if sev.get("leaf_found") else None)
    if not info:
        st.caption(t(lang, "advice_unavailable"))
        return
    ti = info["section_titles"]
    if not info["translation_reviewed"] and ti.get("translation_note"):
        st.caption(ti["translation_note"])
    components.html(speech.speech_html([info["name"], info["description"], *info["severity_advice"]], lang,
                                       t(lang, "read_aloud"), t(lang, "read_note")), height=96)
    st.markdown(info["description"])
    if info["severity_advice"]:
        st.markdown(f"**{ti['actions']}**")
        bullets(info["severity_advice"])
    for key in ("symptoms", "causes"):
        if info[key]:
            st.markdown(f"**{ti[key]}**")
            bullets(info[key])
    mg = info["management"]
    if any(mg.values()):
        st.markdown(f"**{ti['management']}**")
        for key in ("cultural", "organic", "chemical"):
            if mg[key]:
                st.markdown(f"*{ti[key]}*")
                bullets(mg[key])
    if info["prevention"]:
        st.markdown(f"**{ti['prevention']}**")
        bullets(info["prevention"])
    st.markdown(f"**{ti['growth']}**")
    for key in ("nutrient", "water", "spacing", "monitoring"):
        if info["growth"][key]:
            st.markdown(f"*{ti[key]}*")
            bullets(info["growth"][key])
    st.markdown(f"**{ti['sources']}**")
    st.caption(ti["sources_note"])
    for s in info["sources"]:
        st.markdown(f"- [{s['org']}: {s['title']}]({s['url']})")
    st.warning(info["disclaimer"])


def show_pdf_button(last):
    """Create-then-download flow: the PDF is built on demand (and again if the language changes)."""
    pdf = st.session_state.get("pdf")
    if pdf and pdf["id"] == last.get("id") and pdf["lang"] == lang:
        st.download_button(t(lang, "pdf_download"), data=pdf["bytes"], file_name="rice-leaf-report.pdf",
                           mime="application/pdf", use_container_width=True, type="primary")
    elif last.get("image_bytes") and st.button(t(lang, "pdf_prepare"), use_container_width=True):
        with st.spinner(t(lang, "pdf_preparing")):
            try:
                data = api_client.report(last["image_bytes"], last.get("filename") or "photo.jpg", last["result"], lang)
                st.session_state.pdf = {"id": last.get("id"), "lang": lang, "bytes": data}
                st.rerun()
            except (api_client.BackendDown, api_client.BackendError):
                st.error(t(lang, "pdf_error"))


last = st.session_state.last
if last:
    with st.container(border=True):
        kind = last["kind"]
        if kind == "no_image":
            st.info(t(lang, "no_image"))
        elif kind == "backend_down":
            st.error(t(lang, "backend_down"))
        elif kind == "model_not_ready":
            show_quality(last.get("quality"))
            st.info(t(lang, "model_not_ready"))
            if last.get("reason"):
                st.caption(last["reason"])  # technical detail, English only
        elif kind == "bad_image":
            st.error(f"{t(lang, 'bad_image')}: {last['message']}")
        elif kind == "error":
            st.error(t(lang, "generic_error"))
        elif kind == "ok":
            r = last["result"]
            show_quality(r.get("quality"))
            prev = session_tools.previous_scan(st.session_state.history, last.get("id"))
            if prev:
                sev_now = r.get("severity") or {}
                now = hist_text({"disease": "—" if r.get("rejected") else r.get("label", "—"),
                                 "severity": sev_now.get("level") if sev_now.get("leaf_found") else "—"})
                st.caption(t(lang, "prev_line").format(when=prev["date"], disease=hist_text(prev), sev="", now=now))
            with st.expander(t(lang, "result_diagnosis"), expanded=True):
                if r.get("rejected"):
                    st.warning(t(lang, "unsure"))
                    for reason in r.get("reject_reasons", []):
                        st.caption(t(lang, f"reason_{reason}"))
                else:
                    st.subheader(disp(r.get("label", "—")))
                    st.metric(t(lang, "confidence"), f"{r.get('confidence', 0) * 100:.1f}%")
                if r.get("top3"):
                    # when the app refuses, the alternatives must not look like a diagnosis
                    st.markdown(f"**{t(lang, 'closest') if r.get('rejected') else t(lang, 'top3')}**")
                    for item in r["top3"]:
                        st.progress(float(item["confidence"]), text=f"{disp(item['label'])}: {item['confidence'] * 100:.1f}%")
            with st.expander(t(lang, "result_heatmap")):
                if r.get("heatmap_png_b64"):
                    st.image(base64.b64decode(r["heatmap_png_b64"]), use_column_width=True)
                    st.caption(t(lang, "heatmap_explain").format(label=disp(r.get("label", ""))))
                else:
                    st.caption(t(lang, "heatmap_rejected" if r.get("rejected") else "heatmap_unavailable"))
            with st.expander(t(lang, "result_severity")):
                show_severity(r)
            if not r.get("rejected") and r.get("label"):
                with st.expander(t(lang, "result_recommendations")):
                    show_advice(r)
            show_pdf_button(last)


# ---- Session history --------------------------------------------------------
with st.container(border=True):
    st.subheader(t(lang, "history_title"))
    if st.session_state.history:
        labels = {
            "date": t(lang, "col_date"),
            "disease": t(lang, "col_disease"),
            "confidence": t(lang, "col_conf"),
            "severity": t(lang, "col_severity"),
        }
        # Plain Markdown table instead of st.dataframe: that needs pandas + pyarrow, whose DLL
        # is blocked by some Windows Application Control policies (it crashed on this project's dev PC).
        keys = list(labels)
        table = ["| " + " | ".join(labels[k] for k in keys) + " |", "|" + " --- |" * len(keys)]
        for row in reversed(st.session_state.history):  # newest first
            shown = {**row, "disease": t(lang, "not_diagnosed") if row["disease"] == "—" else disp(row["disease"]),
                     "severity": sev_text(row["severity"])}
            table.append("| " + " | ".join(str(shown[k]).replace("|", "/") for k in keys) + " |")
        st.markdown("\n".join(table))
        summ = session_tools.summarize(st.session_state.history)
        st.markdown(f"**{t(lang, 'summary_title')}**")
        summary_line = t(lang, "summary_line").format(total=summ["total"], ok=summ["diagnosed"], rej=summ["refused"])
        if summ["most_common"]:
            summary_line += " · " + t(lang, "summary_common").format(name=disp(summ["most_common"][0]), n=summ["most_common"][1])
        st.caption(summary_line)
        st.download_button(t(lang, "export_csv"), data=session_tools.history_csv(st.session_state.history, disease_names),
                           file_name="rice-leaf-history.csv", mime="text/csv", use_container_width=True)
        if st.button(t(lang, "clear_history"), use_container_width=True):
            st.session_state.history = []
            st.rerun()
    else:
        st.caption(t(lang, "history_empty"))
