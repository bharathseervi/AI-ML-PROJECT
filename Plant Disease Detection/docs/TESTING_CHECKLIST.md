# Testing checklist (Stage 6)

Written for: you, while testing the finished app. Two separate jobs:

* **Part A: real-world accuracy test** with 20-30 of your own phone photos. **Decision for this project: NOT performed** (photographing and expert-labelling rice plants was not possible), and the report says so (Section 6.5). Part A is kept as the protocol for future work. You can still do its small, field-free parts: the non-rice photos and the bad-quality photos (A5).
* **Part B: functional and usability checklist** for every feature of the app.

You can do Part B now (the app runs without a trained model, but it will answer "model not ready"). Part A needs the trained models in `models/`.

---

## Part A: real-world test with your own photos (OPTIONAL, not performed in this project)

### A1. Plan the photos (aim for 25-30)
| What | How many | Notes |
|---|---|---|
| Diseased leaves of the diseases you can actually find | at least 3-4 per disease | Only include a disease if you can get it **confirmed by an expert**. Leaf Smut and Tungro may be hard to find in your season. It is fine to test fewer classes; say which ones in the report. |
| Healthy leaves | 4-5 | From different plants and fields. |
| **Non-rice** photos (a hand, weeds, another crop, soil) | 3-5 | Tests the "unable to diagnose" rejection. Label them `NotRice`. |

* **Different plants, not many photos of one plant.** Photos of one plant are not independent test cases. Use the `plant_id` column to note which plant each came from. Aim for at least 20 distinct plants.
* **Vary the conditions on purpose:** sunny and shaded, morning and afternoon, plain background (your hand or paper) and busy field background, 2-3 different phones if you can. The app asks for plain background and natural light; real users will not always do that.
* **Take photos the way a farmer would.** Use the phone's normal camera, hold it steady, one leaf per photo, spots filling most of the frame. Do **not** edit or crop. Do not retake a photo because the app got it wrong.
* **Do not look at the app's answer before you label.** Labelling a photo after seeing the app's answer biases the test.

### A2. Get the true labels from a person who knows
The label must come from an agriculture officer, a KVK scientist, or an experienced farmer, **not from the app and not from a web search of the photo**. Write down who confirmed each label (`confirmed_by`). If the expert says "I am not sure", leave that photo out (`include` = `no`) and note it. Say in the report how labels were confirmed; a panel will ask.

### A3. Put the photos in a folder and create the label sheet
```powershell
# put the photos in e.g. C:\...\Plant Disease Detection\my_photos\
.\.venv\Scripts\python.exe scripts\eval_real_photos.py my_photos --init-template
```
This creates `my_photos\labels.csv`. Open it in Excel and fill in:

| Column | What to write |
|---|---|
| `file` | filled in for you |
| `true_label` | `Blast`, `Brown Spot`, `Healthy`, `Leaf Smut`, `Sheath Blight`, `Tungro`, or `NotRice` |
| `include` | leave `yes`, or `no` to skip a photo (for example the deliberately bad quality-test photos in A5) |
| `plant_id` | any name that is the same for photos of the same plant (`p1`, `p2` ...) |
| `confirmed_by`, `phone`, `date`, `place` | for your report |
| `lighting`, `background` | short words such as `sun` / `shade`, `plain` / `field`. If you fill these, the script shows accuracy per group. |
| `notes` | anything |

### A4. Run it
Start with the models in `models/` (copied from Colab), then:
```powershell
.\.venv\Scripts\python.exe scripts\eval_real_photos.py my_photos
```
Or, to test through the real Flask server (start `.\run_dev.ps1` first):
```powershell
.\.venv\Scripts\python.exe scripts\eval_real_photos.py my_photos --api http://127.0.0.1:5000
```
**Expected output:** one line per photo (`OK` or `MISS`), then a summary and a folder `results\real_photos_<time>\` with `summary.md`, `per_photo.csv`, `confusion.csv`.

**Common errors**
| Message | Fix |
|---|---|
| `No trained model available: Missing in models/ ...` | Copy `class_names.json`, `calibration.json` and the two `.pt` files from Colab into `models\`. |
| `labels.csv has problems: row 5 ... unknown label` | The label text must be exactly one of the names above (capital letters do not matter). |
| `true_label is empty` | Fill every row, or set `include` to `no`. |
| `file ... not found` | The file name in the sheet must match the file in the folder. |
| `Cannot reach the API` | Start `run_dev.ps1`, or leave out `--api`. |

### A5. Quality-check test (do separately, by hand, not in the accuracy numbers)
Take 3 deliberately bad photos of a leaf (shaky or out of focus; in the dark; in harsh glare) and upload them. Write down whether the app warned and whether the warning was right. If real bad photos are **not** flagged (or good photos are flagged), tell me which ones and we will re-tune the thresholds in `backend/config.py`. They were set on artificially damaged copies, not on real bad photos.

### A6. What to write in the report (section 6.5)
* Paste `summary.md`. Quote the **interval**, not just the percentage: with about 25 photos, 22 correct (88%) means the true accuracy is plausibly 70% to 96%.
* Say how many photos, how many distinct plants, which diseases, which phones, where and when, and **who confirmed the labels**.
* Compare with the dataset test result and **explain the difference honestly**. A drop is normal and expected (one region and season in the training data, different phones and lighting). Do not hide it and do not average it with the dataset result.
* Include the confusion table, the mistakes list, and how many non-rice photos were refused.
* If the app is overconfident on mistakes, say so; the table shows the confidence of each mistake.

---

## Part B: functional and usability checklist

Mark each row Pass / Fail / Not applicable and write what you saw. Run the app with `.\run_dev.ps1` and open `http://localhost:8501`.

### B1. Start-up
| # | Test | Expected | Result |
|---|---|---|---|
| 1 | Open the app with the backend running | Page loads; sidebar says "Server connected" | |
| 2 | Open the app with the backend **stopped** | Friendly message "Cannot reach the server", no crash or traceback | |
| 3 | Run with no trained model | After Diagnose, an info message "model not trained yet"; photo-quality warnings still appear | |

### B2. Input and preprocessing
| # | Test | Expected | Result |
|---|---|---|---|
| 4 | Upload a JPG | Preview shown; Diagnose works | |
| 5 | Upload a PNG | Same | |
| 6 | Upload a `.pdf` or `.txt` | Rejected with a clear message | |
| 7 | Upload a text file renamed to `.jpg` | Rejected ("could not be read as an image") | |
| 8 | Upload a photo larger than 10 MB | Rejected with a size message | |
| 9 | Upload a phone photo taken in **portrait** | Result is the right way up (EXIF rotation applied) | |
| 10 | Switch to **Camera** and take a photo (on `localhost` the browser allows it) | Same result flow as upload | |
| 11 | Click Diagnose with no photo | "Add a photo first" | |

### B3. Photo quality
| # | Test | Expected | Result |
|---|---|---|---|
| 12 | A blurry photo | "The photo looks blurry..." warning | |
| 13 | A very dark photo | "too dark" warning | |
| 14 | A bright or glary photo | "overexposed" warning | |
| 15 | A normal photo | No quality warning | |

### B4. Diagnosis (needs trained models)
| # | Test | Expected | Result |
|---|---|---|---|
| 16 | A clear diseased leaf | Disease name, confidence, top-3 | |
| 17 | A healthy leaf | "Healthy"; severity says not calculated | |
| 18 | A non-rice photo | "Unable to diagnose reliably" + reason + retake tips | |
| 19 | The heatmap | Shown with a one-line explanation; check the glow is on the leaf, not the background | |
| 20 | The severity section | Number + overlay + the "EXPERIMENTAL" warning | |
| 21 | Response time on your laptop | Note the seconds for the first and second photo | |

### B5. Languages and advice
| # | Test | Expected | Result |
|---|---|---|---|
| 22 | Switch English -> Kannada -> Hindi on a result | Labels, disease name, advice and severity level all change | |
| 23 | Open "Treatment and growth advice" | Description, symptoms, causes, cultural / organic / chemical, prevention, growth, sources | |
| 24 | Read the chemical section | No doses; says follow the product label and ask the officer or KVK | |
| 25 | Kannada and Hindi text on screen | Letters and conjuncts look right; a native speaker has reviewed them (not yet done) | |
| 26 | The notice on Kannada / Hindi advice | Says the translation is unreviewed | |

### B6. PDF report
| # | Test | Expected | Result |
|---|---|---|---|
| 27 | Click "Create PDF report", then Download | A PDF downloads (about 3 pages) | |
| 28 | Open the English, Kannada and Hindi PDFs | Photo, heatmap, diagnosis, severity, advice, sources, date, disclaimer; Kannada and Hindi letters correct | |
| 29 | Create a PDF for a rejected photo | Says "unable to diagnose", gives retake tips, **no** treatment advice | |
| 30 | Change language after creating a PDF | The old PDF is not offered in the new language; "create" button reappears | |

### B7. History, layout, theme
| # | Test | Expected | Result |
|---|---|---|---|
| 31 | Diagnose 3 photos | History table lists date, disease, confidence, severity (newest first) | |
| 32 | Switch language | Disease names in the history table change | |
| 33 | Clear history | Table empties | |
| 34 | Light and dark mode (top-right menu, Settings) | Everything readable in both | |
| 35 | Open on a phone browser on the same Wi-Fi (`http://<laptop-ip>:8501`) or narrow the browser to about 400 px | Single column, big buttons, no sideways scrolling. **The phone camera will not work on plain http**, which is expected for a local run; upload still works | |
| 36 | Collapsible sections | Diagnosis, heatmap, severity, advice open and close | |

### B8. Automated tests
```powershell
.\.venv\Scripts\python.exe -m pytest
```
**Expected:** all tests pass (about 150). If one fails, paste the message to me.

---

## Honest limits to state in your report
* Photos are a small sample from your area; the interval is wide.
* Labels confirmed by [[WHO]]; some diseases may be missing because they were not available.
* Quality thresholds were set on artificially damaged photos (Part A5 checks them on real ones).
* Kannada and Hindi text and the agronomy advice are not yet reviewed by experts.
