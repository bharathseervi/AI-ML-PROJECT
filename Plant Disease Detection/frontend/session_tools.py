"""Pure helpers for the session history: CSV export, summary, and the previous scan. No Streamlit here, so they are unit-tested."""
import csv
import io
from collections import Counter

NOT_DIAGNOSED = "—"
LEVELS = ("Mild", "Moderate", "Severe")


def history_csv(history: list[dict], names: dict | None = None) -> bytes:
    """CSV (UTF-8 with a BOM so Excel shows Kannada and Hindi correctly). Disease and severity are written in English
    (stable values), plus the local disease name for reading."""
    names = names or {}
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["date", "diagnosed", "disease", "disease_local_name", "confidence_percent", "severity_estimate_experimental"])
    for row in history:
        diagnosed = row["disease"] != NOT_DIAGNOSED
        conf = str(row.get("confidence", "")).replace("%", "").strip()
        sev = row.get("severity", "")
        w.writerow([row.get("date", ""), "yes" if diagnosed else "no", row["disease"] if diagnosed else "",
                    names.get(row["disease"], "") if diagnosed else "", conf, sev if sev in LEVELS else ""])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def summarize(history: list[dict]) -> dict:
    diagnosed = [r["disease"] for r in history if r["disease"] != NOT_DIAGNOSED]
    common = Counter(diagnosed).most_common(1)
    return {"total": len(history), "diagnosed": len(diagnosed), "refused": len(history) - len(diagnosed),
            "most_common": common[0] if common else None, "by_disease": dict(Counter(diagnosed))}


def previous_scan(history: list[dict], scan_id: str | None) -> dict | None:
    """The scan made just before the one with this id (or before the newest one if the id is unknown)."""
    if not history:
        return None
    ids = [r.get("id") for r in history]
    idx = ids.index(scan_id) if scan_id in ids else len(history) - 1
    return history[idx - 1] if idx >= 1 else None
