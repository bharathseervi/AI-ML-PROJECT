# Rice Leaf Disease Detection (Streamlit + Flask)

Decision-support tool only. It does not replace an agriculture expert.

Status: **Working with trained models.** The models were trained on Colab (T4) and installed in `models/`; the full app runs locally with real diagnoses, heatmaps, severity, advice in three languages and PDF reports. Measured on the dataset's test split (1,392 photos): ensemble accuracy **75.1%**, macro-F1 0.733 (EfficientNetV2-S alone 75.5%, so the ensemble gave no measurable gain; it is kept because it is better calibrated, was the project brief, and its rejection thresholds were measured). The rejection rule answers about 50% of photos at about 93% accuracy. Weakest class: Leaf Smut (F1 about 0.38). Still to do: test on your own phone photos, expert review of the advice, native-speaker review of Kannada/Hindi, and the report placeholders. See `docs/`.

Dataset: **RiceLeafDiseaseBD** (field smartphone photos, Gazipur, Bangladesh, CC BY 4.0). 6 classes: Blast, Brown Spot, Healthy, Leaf Smut, Sheath Blight, Tungro. The app adds an "unsure" outcome through rejection logic.

## Layout
| Path | Purpose |
|---|---|
| `backend/` | Flask API: `app.py` (routes), `config.py` (class list, quality and severity thresholds), `services/`: `image_io.py` (validation, EXIF fix, downscale, RGB), `quality.py` (blur / dark / overexposed), `inference.py` (ensemble, temperature scaling, rejection), `gradcam.py`, `severity.py` (HSV), `pdf_report.py` + `typeset.py` (PDF with Kannada/Hindi). `disease_info.py` is the knowledge base. `assets/fonts/` holds the Noto fonts (OFL) |
| `frontend/` | Streamlit UI: `app.py`, `api_client.py`, `i18n.py` (EN/KN/HI), `.streamlit/config.toml` |
| `scripts/prepare_dataset.py` | Shrinks the 5.6 GB dataset to a 477 MB zip for Colab (uses `Original images/` only) |
| `notebooks/train_rice_classifier.ipynb` | Colab notebook: clean, split, train 3 models, evaluate, calibrate, export. Generated from the `.py` next to it |
| `models/` | Exported weights + `class_names.json` + `calibration.json` go here |
| `tests/` | `pytest` suites for backend and frontend |
| `run_dev.ps1` | Starts both servers |

## Setup (Windows, PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -r backend/requirements-nodeps.txt   # grad-cam without its opencv dependency
```
The first command downloads PyTorch (about 200 MB) and takes a few minutes.

## Run the app
```powershell
.\run_dev.ps1          # Flask on :5000, Streamlit on :8501 -> open http://localhost:8501
```
Test: `.\.venv\Scripts\python.exe -m pytest`

## Training (Stage 1)
1. **Prepare the data on your PC** (about 2 minutes):
   ```powershell
   .\.venv\Scripts\python.exe scripts\prepare_dataset.py
   ```
   Output: `data_prepared\RiceLeaf_320.zip` (477 MB, 9,769 images). Expected last lines: `Images kept: 9769   skipped: 0`.
2. **Upload** that zip to Google Drive at `MyDrive/rice_project/data/RiceLeaf_320.zip`.
3. **Colab:** upload `notebooks/train_rice_classifier.ipynb`, set Runtime > Change runtime type > **T4 GPU**, then run the cells top to bottom (it mounts Drive and asks for permission).
4. **Train in this order:** ResNet-18 baseline, then EfficientNetV2-S, then Swin-T (one cell each). Each model resumes automatically if Colab disconnects: reconnect and re-run all cells from the top.
5. Run the evaluation cells, then the export cell. Download these 4 files from `MyDrive/rice_project/export/` into this project's `models/` folder: `class_names.json`, `efficientnetv2s.pt`, `swin_t.pt`, `calibration.json`.

What the notebook does (all checked on the real data split, not yet on a real training run):
- Drops unreadable files, byte-identical copies, and copies that carry conflicting labels.
- Groups near-duplicates (perceptual hash, including mirrored copies) **and photos of one class taken within 10 s of each other** (same leaf or plant), then splits stratified 70/15/15 so no group crosses splits. The split lists are saved to Drive and reused.
- Trains two-stage (head, then full network) with mixed precision, label smoothing, class weights, cosine LR, gradient clipping, early stopping on validation macro-F1. Augmentation is training-only.
- On the test split only: accuracy, per-class and macro precision/recall/F1, confusion matrices, curves, parameters, model size, CPU latency, one comparison table, temperature scaling with ECE and reliability plots, rejection thresholds chosen on validation, error analysis.
- Estimated time on a T4 (**estimates, not measurements**): ResNet-18 8-12 min, EfficientNetV2-S 17-26 min, Swin-T 15-23 min. The notebook prints the true seconds per epoch.

## API
| Endpoint | Behaviour |
|---|---|
| `GET /api/health` | `{status, model_loaded, model_reason, classes}` |
| `POST /api/predict` | multipart field `image` (JPG/JPEG/PNG, max 10 MB). 400 bad file, 413 too large, 503 model not ready (body still includes `quality`), 200 result |
| `GET /api/info?label=Blast&lang=kn&severity=Moderate` | Knowledge-base text for one diagnosis in one language (404 for an unknown label) |
| `GET /api/classes?lang=kn` | Localised disease names |
| `POST /api/report` | multipart: `image`, `result` (the JSON from `/api/predict`), `lang` (en/kn/hi) returns a PDF. 400 for a bad photo or result |

200 body of `/api/predict`:
```json
{"label": "Blast", "confidence": 0.0, "rejected": false, "reject_reasons": [], "entropy": 0.0,
 "top3": [{"label": "Blast", "confidence": 0.0}],
 "heatmap_png_b64": "...", "heatmap_model": "efficientnetv2s",
 "severity": {"leaf_found": true, "percent": 0.0, "level": "Mild", "overlay_png_b64": "..."},
 "quality": {"ok": true, "issues": [], "blur_score": 0.0, "brightness": 0.0, "saturated_frac": 0.0},
 "models_used": ["efficientnetv2s", "swin_t"], "image": {"width": 1024, "height": 1024}}
```
If `rejected` is true, `label`, heatmap and severity are `null` (the top-3 is still listed). Severity is `null` for a healthy leaf.

## How the prediction works (Stage 2)
1. Each model gets the photo squashed to a square (as in training), gives logits, which are divided by that model's **temperature** (fitted on validation data) and softmaxed. The two models' probabilities are averaged.
2. **Rejection:** the answer is "unable to diagnose" if confidence is below `min_confidence` **or** normalised entropy is above `max_normalised_entropy`. Both numbers come from `models/calibration.json`, which the notebook writes after choosing them on the **validation** split (confidence so that accepted validation predictions reach 95% accuracy; entropy limit = 95th percentile among correct validation predictions). Random-weight test models can never reach those numbers, so thresholds are only meaningful once trained.
3. **Grad-CAM** runs on the first CNN in the ensemble (EfficientNetV2-S) only, to keep CPU time low. It explains that model, not the whole ensemble.
4. **Severity** (HSV colour segmentation) runs only for an accepted, non-healthy answer.

## Measured results from Stage 2 testing (no model involved; real photos from RiceLeafDiseaseBD)
**Photo-quality thresholds** (`scripts/measure_quality_thresholds.py`, 1,500 photos). Real dataset photos: blur score p0.5 = 99, mean brightness 89-155. Chosen: blurry below 40, too dark below 60, overexposed above mean 200 or above 10% near-white pixels. These flag 0% of real photos and catch most artificially damaged copies (Gaussian blur sigma 4: 100%; darkened x0.35: 99.8%; sigma 2 blur: 49%; brightened x1.8: about 26-72%). **Caveat:** the dataset contains almost no bad photos, so these are conservative starting points. Re-check them with your own blurry and dark phone photos in Stage 6.

**Severity is NOT reliable on field photos.** This is a measured finding:
- Healthy leaves scored a median of about 5% "affected" (90th percentile about 14%): that is the noise floor.
- Correlation with the dataset's hand-drawn lesion boxes was about zero (Spearman -0.04 on 398 photos); healthy and diseased photos received the same median.
- Three alternative colour rules and a background-complexity guard did not fix it.
- Likely reason: most Blast and Brown Spot lesions are tiny (median annotated box about 1.4% of the image), about the same size as the noise, and busy backgrounds add false "lesions".
- On clean synthetic leaves with a known affected area it measures correctly (`tests/test_severity.py`), so the arithmetic is right; what fails is telling lesions from background and texture in real photos.
- The app therefore labels severity **experimental**, always shows the overlay (red = counted as lesion) so the user can judge, and says values under about 10% may be noise. Mild/Moderate/Severe cut-offs (10% and 25%) are this project's own choice, not an official scale.
- Better future approach: train a lesion detector on the dataset's YOLO boxes (the dataset is designed for this) and measure lesion area or count from that.
- Check it yourself: `.\.venv\Scripts\python.exe -m backend.services.severity photo1.jpg photo2.jpg --out severity_check` writes overlays and a CSV.

## Dataset findings (measured on the real data)
- 39 byte-identical duplicate groups. 8 of them (16 images, mostly Tungro vs Sheath Blight) carry **conflicting class labels**. Cleaning leaves 9,720 of 9,769 images.
- Photos were squashed from 3:4 to 1:1 by the dataset authors. The app must resize to a square the same way (no crop, no padding).
- One region and one season. Test accuracy on this dataset will not equal accuracy on Karnataka fields; Stage 6 reports your own phone photos separately.

## Known notes
- Kannada and Hindi UI text is AI-written and **needs native-speaker review** (`frontend/i18n.py`).
- History is a Markdown table, not `st.dataframe`: pandas/pyarrow DLLs are blocked by this PC's Windows Application Control policy. The same policy intermittently blocks scikit-learn here, which is why local testing of training used a small sample (Colab is unaffected).
- The camera needs `localhost` or HTTPS.
- Deployment: **none.** This is a local project (decided by the user), so there is no Hugging Face, Docker or hosting work. Run it with `run_dev.ps1`. The phone camera works on `localhost`; to try it from a phone you would need HTTPS, which a local run does not provide.
- Library pins used for training: `timm==1.0.9` needs `huggingface_hub<1` (done in the notebook's first cell).

## Knowledge base and PDF report (Stage 3)
- **Content** lives in `backend/disease_info.py`: for Blast, Brown Spot, Tungro, Sheath Blight, Leaf Smut and Healthy, in English, Kannada and Hindi: description, symptoms, causes and favouring conditions, cultural / organic / chemical management, prevention, and growth recommendations (nutrient, water, spacing, monitoring), plus advice by severity level. A shared safety line is appended to every "chemical" list.
- **Sources:** IRRI Rice Knowledge Bank and TNAU Agritech Portal pages, listed in each report. I could read these through web search summaries only (direct page fetches were blocked), so **check the content against the pages themselves**. **Leaf Smut** has no IRRI/TNAU page I could find; its text comes from Texas A&M and University of Arkansas extension pages, and says so. No pesticide doses appear anywhere (a test enforces this).
- **Not reviewed:** the agronomy has not been checked by an agronomist, and the Kannada and Hindi text (including disease names) is AI-written and needs native-speaker review. The app and PDF say so in those languages.
- **Report:** one PDF per plant (photo, heatmap, diagnosis, confidence, top 3, severity, advice, sources, date, disclaimer on the last page and a short one in every footer). For "unable to diagnose" it contains the retake tips and no treatment advice.
- **Kannada/Hindi in the PDF:** ReportLab cannot shape Indic scripts, so `typeset.py` shapes text with HarfBuzz and draws the glyph outlines as vectors. Output renders conjuncts correctly (checked by eye on rendered pages) and stays sharp, but that text is **not selectable or searchable**. English is normal text. Bold is simulated.
- **Found by running it live:** the real `/api/predict` response is about 0.6 MB, over Werkzeug's default 500 KB form-field cap, which made `/api/report` return 413. Fixed (limit raised to 4 MB, pinned `werkzeug==3.1.9`, covered by a test).
- **Tests:** 130+ tests (`pytest`), including every disease in every language building a valid PDF.

## Testing and documents (Stages 6-7)
- `docs/TESTING_CHECKLIST.md`: how to collect and label 20-30 of your own phone photos, plus a pass/fail checklist for every app feature.
- `scripts/eval_real_photos.py`: scores your own photos **separately from the dataset test split**. Creates the label sheet (`--init-template`), then reports strict accuracy, accuracy on answered photos, rejection behaviour, per-class results, a confusion table and mistakes, with **95% confidence intervals** (with about 25 photos, 88% accuracy really means roughly 70-96%). Works in-process or through the running API (`--api`). Sanity check: random stand-in models score about 17%, which is chance level for six classes.
- `docs/PROJECT_REPORT.md`: report text with measured facts filled in and `[[placeholders]]` for your Colab and real-photo numbers.
- `docs/SLIDES_AND_DEMO.md`: slide outline, 5-minute demo script and viva questions.

## Extras added after the first release
- **App:** download the session history as CSV (opens correctly in Excel, including Kannada and Hindi), a session summary (photos, diagnosed, not diagnosed, most common disease), a note comparing with the previous scan in the session, and a **Read aloud** button (uses the browser's own voice; a voice for Kannada or Hindi must be installed on the device, and Kannada voices are missing on many systems). Code: `frontend/session_tools.py`, `frontend/speech.py`.
- **Analysis from the saved Colab predictions** (`scripts/analyze_results.py`, no GPU): cluster-bootstrap confidence intervals (the ensemble and EfficientNetV2-S are indistinguishable on overall accuracy, 75.1% vs 75.5%, but the ensemble is about 5 points better on the 50% of photos it is most sure of), the rejection rule compared across models, and a label-noise audit (about 13.5% suspect labels, an unconfirmed estimate inflated by repeated shots of the same leaf). Output: `results/analysis/`. Summarised in `docs/PROJECT_REPORT.md` Sections 6.1, 6.3 and 6.4.
- **Tried and dropped:** a "move the camera closer" warning based on how much of the frame the leaf fills. On the 1,392 test photos it had no relationship with accuracy (correlation -0.01), so it was not added. Test-time augmentation and further training experiments were not pursued.
- **Checked:** this PC reproduces the Colab model's predictions (logit differences under 0.01, identical predicted classes on a sample), which validates the exported model files and preprocessing.

## Look and feel
- The page uses the photo `frontend/static/background.jpg` (a copy of `rice picture.jpg`) as its background, with a darkening overlay, glass-style cards, rounded controls, a green gradient primary button, an animated card entrance (switched off for users who prefer reduced motion), a live server-status chip, and an in-app **Dark mode** switch. All styling is in `frontend/theme.py`.
- Screenshots taken from the running app in Edge (desktop light and dark, phone width, Kannada) are in `docs/screenshots/`.
- **The background photo carries visible Vecteezy watermarks.** Check the licence before you publish or hand in anything that shows it; stock sites normally require a licence or attribution for the unwatermarked version. Replace `frontend/static/background.jpg` with another image to change it.
- **Streamlit settings** now live in `.streamlit/config.toml` at the project root (Streamlit reads it from the folder it is started in; the old copy inside `frontend/` was never read, so the 10 MB upload limit was not applied). `run_dev.ps1` starts Streamlit from the project root.
- The theme was checked in a real browser with Playwright (a development-only tool, not in the requirements): it found and fixed a card style that wrapped the whole page, an invisible header that blocked clicks, and unreadable dark-mode controls. The 11 theme tests check the CSS and the config; the visual result was checked by eye.
