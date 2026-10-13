"""Convert a '# %%' percent-format .py file into a Colab-ready .ipynb (stdlib only).

    python scripts/py_to_ipynb.py notebooks/train_rice_classifier.py

'# %%' starts a code cell, '# %% [markdown]' a markdown cell (its '# ' prefixes are stripped).
The .py file stays the source of truth: edit it, then regenerate the notebook.
"""
import json
import sys
from pathlib import Path


def convert(src: Path) -> Path:
    cells, kind, buf = [], None, []

    def flush():
        if kind is None:
            return
        lines = list(buf)
        while lines and not lines[-1].strip():
            lines.pop()
        if kind == "markdown":
            lines = [ln[2:] if ln.startswith("# ") else ("" if ln.strip() == "#" else ln) for ln in lines]
        text = "\n".join(lines)
        if not text.strip():
            return
        cell = {"cell_type": kind, "metadata": {}, "source": text.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)

    for line in src.read_text(encoding="utf-8").splitlines():
        if line.startswith("# %%"):
            flush()
            kind, buf = ("markdown" if "[markdown]" in line else "code"), []
        elif kind is not None:
            buf.append(line)
    flush()

    nb = {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": [], "gpuType": "T4"},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }
    out = src.with_suffix(".ipynb")
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    out = convert(Path(sys.argv[1]))
    print("wrote", out)
