# Slide outline, 5-minute demo script and viva preparation

Written for: you, presenting to your guide and the evaluation panel. `[[...]]` = fill with your real numbers after training. Never present a number you did not measure.

---

## Part 1: Slide outline (12 slides, about 8-10 minutes with a demo; trim to 8 for a 5-minute slot)

| # | Slide | What to put on it | Say (key points) |
|---|---|---|---|
| 1 | **Title** | Project title, your name, guide, college | One sentence: "A web app where a farmer photographs a rice leaf and gets a diagnosis, evidence, and advice, in Kannada, Hindi or English." |
| 2 | **Problem** | Photo of diseased leaf; 3 bullets: diseases look alike, experts not always available, wrong spraying costs money | Why this matters. Don't quote yield-loss statistics unless you have a source. |
| 3 | **What the app does** | Flow diagram: Photo -> quality check -> diagnosis -> reject if unsure -> heatmap -> severity -> advice -> PDF | Six outputs in one pass. |
| 4 | **Dataset** | Class table (9,769 images, 6 classes), 2 sample photos. Note: field smartphone photos, Bangladesh, 2025 | "Real field photos, not lab images, so closer to real use." |
| 5 | **Data problems we found** | 39 duplicate groups; **8 groups (16 images) with conflicting labels** (same photo under two diseases); we removed them. 9,769 -> 9,720. Also show Figure 4 (docs/figures/misclassified_examples.png): what looks like the same leaf labelled Brown Spot in one photo and Leaf Smut in two others | This is a strong slide: you checked the data, not just trained on it. |
| 6 | **Avoiding leakage** | Split diagram: group near-duplicates and photos taken within 10 s; 70/15/15; "no group in two splits" | "Otherwise accuracy would be inflated." |
| 7 | **Models** | ResNet-18 (baseline), EfficientNetV2-S, Swin-T, ensemble; two-stage fine-tuning; Colab T4 | Why two different architectures: a CNN and a transformer make different mistakes. |
| 8 | **Results** | The comparison table: ResNet-18 71.2%, EfficientNetV2-S 75.5%, Swin-T 71.1%, Ensemble 75.1% (macro-F1 0.70 / 0.74 / 0.70 / 0.73); confusion matrix image | Say it plainly: on overall accuracy the ensemble did NOT beat EfficientNetV2-S alone (75.1% vs 75.5%, 95% CIs about 69-81%, so no real difference), but on the photos the app actually answers (the 50% it is most sure of) it is about 5 points better (93.0% vs 88.1%). Best classes: Sheath Blight 0.92 F1, Tungro 0.89. Weakest: Leaf Smut 0.38. |
| 9 | **Knowing when not to answer** | Reliability diagram (ECE 0.056 -> 0.046 for the ensemble); reject rule: confidence at least 0.845 and entropy at most 0.683; on the test split it answers 50.5% of photos at 92.7% accuracy and refuses 85.3% of the model's wrong answers | "A confident wrong answer is worse than 'retake the photo'." |
| 10 | **What we did not test** | One bullet: no field test on our own photos. One bullet: all numbers are on the dataset's own test split (same region and season). One bullet: the rejection rule is the safety net; field testing is future work | Say it first, before a panel member asks. It shows you understand the limit. |
| 11 | **Limits and an honest negative result** | Severity: healthy leaves scored about 5% too, correlation about 0. Single region. Translations unreviewed. | "We reported where it fails." Panels respect this. |
| 12 | **Future work + conclusion** | Lesion detector from the dataset's boxes; Karnataka photos; expert review; "a decision-support tool, not a replacement for an agriculture expert" | End on the disclaimer. |

**Slide design tips:** one idea per slide; show images, not paragraphs; put the confusion matrix and the reliability diagram on their own slides if you have time.

---

## Part 2: 5-minute live demo script

**Before you start (do this 10 minutes earlier):**
1. Run `.\run_dev.ps1`, open `http://localhost:8501`.
2. Check the sidebar says "Server connected".
3. Pick **4 photos** ready on the desktop: (a) a clear diseased leaf the model gets right, (b) a healthy leaf, (c) a **blurry or dark** photo, (d) a **non-rice photo** (hand, other plant) to show rejection.
4. Pre-generate one PDF in English and one in Kannada or Hindi, saved on the desktop, as a backup.
5. Take **screenshots** of a full run, in case the laptop misbehaves.

| Time | Do | Say |
|---|---|---|
| 0:00-0:30 | Show the home page, language dropdown, photo-tips box | "A farmer picks a language, reads the photo tips, then uploads a photo or uses the camera." |
| 0:30-1:30 | Upload photo (a). Click Diagnose | "It checks photo quality, then two models vote. Here it says [[disease]] with [[x%]] confidence, and shows the top 3." |
| 1:30-2:15 | Open the heatmap section | "The heatmap shows where the model looked. We check it is on the spots, not the background." |
| 2:15-2:45 | Open the severity section | "This is an experimental colour-based estimate. We tested it and found it unreliable on field photos, so we show the overlay and say so." *(Say this yourself before a panel member finds it.)* |
| 2:45-3:30 | Switch language to Kannada/Hindi; open the advice section | "Advice comes from IRRI and TNAU pages, in three languages. No pesticide doses: it tells the farmer to follow the label and ask the local officer or KVK." |
| 3:30-4:00 | Click Create PDF report, download, open the Kannada/Hindi one | "One-page-per-plant report with the photo, heatmap, advice, sources and the disclaimer." |
| 4:00-4:40 | Upload photo (c) blurry, then (d) non-rice | "If the photo is bad it asks for a retake. If the model isn't sure it says 'unable to diagnose reliably' instead of guessing." |
| 4:40-5:00 | Show history table | "Session history shows date, disease, confidence, severity. It's a decision-support tool, not a replacement for an agriculture expert." |

**If something breaks:** say "let me show the recorded run", open your screenshots or the backup PDFs, and carry on. Do not debug in front of the panel.

**Do not claim:** field accuracy (no field test was done); that it works on every field; any accuracy you didn't measure; that severity is accurate; that the translations were checked by a native speaker (they were not, unless you get them reviewed).

---

## Part 3: Likely viva questions, with honest answers

**Q: Why this dataset?** It is made of field smartphone photos, so it is closer to real use than lab-style sets. It also has a healthy class and enough images. Its limit is one region and one season.

**Q: How do you know there is no data leakage?** We removed byte-identical copies, grouped perceptual-hash near-duplicates and photos taken within 10 seconds, split by group, and checked that no group crosses a split. A small residual risk remains for photos of the same plant taken minutes apart.

**Q: Why two models and an ensemble?** A CNN and a transformer look at images differently and tend to make different errors, so averaging probabilities can be more reliable. On overall accuracy it did not: 75.1% against 75.5% for EfficientNetV2-S alone, a difference well inside the noise (paired difference -0.4 points, 95% CI -2.1 to +1.2). But the app refuses unsure photos, and there the ensemble ranks its own answers better: on the 50% of photos it is most confident about it is 93.0% accurate against 88.1% for EfficientNetV2-S (+4.9 points, 95% CI +1.5 to +8.2). That is why we kept it, at the cost of being twice as slow.

**Q: What is temperature scaling and why use it?** Networks tend to be over-confident. One number, fitted on validation data, rescales the outputs so that "90% confident" is right about 90% of the time. We report ECE before and after.

**Q: How did you choose the rejection threshold?** On validation data only: the lowest confidence at which accepted predictions still reach 95% accuracy, plus an entropy limit from the 95th percentile of correct predictions. The test set was not used to choose it.

**Q: Did you test it on real photos of your own?** No. We could not photograph and expert-label diseased rice plants within the project, and we did not want to substitute internet photos whose labels we cannot vouch for. So every number is on the dataset's own test split (same region, season and phones as training). I would expect lower accuracy on other fields. A protocol and a scoring script with confidence intervals are included for a field test, which is the first item of future work.

**Q: Then how do you know it will work in the field?** We do not. What we did: used a field-collected dataset (not lab images), removed duplicate and conflicting photos, split so near-identical photos cannot leak, calibrated the confidence, and added a rule that refuses when unsure (it refuses about half the photos and is right about 93% of the time on the rest). That reduces the risk of confident wrong answers but does not prove field accuracy.

**Q: Why is the accuracy only about 75%?** It is a hard dataset: three of the diseases look alike (brown lesions), labels are visual not lab-confirmed, many lesions are tiny after resizing, and Leaf Smut has few examples. Macro-F1 is 0.73 and per-class results range from 0.92 (Sheath Blight) to 0.38 (Leaf Smut). A higher input resolution and a better-balanced split are untested ideas for improvement.

**Q: How does Grad-CAM work, and can you trust it?** It uses the gradients flowing into the last convolutional stage to weight feature maps and produce a heatmap of influential regions. It is a sanity check: it can reveal the model looking at the background. It does not prove the diagnosis is right. We run it on one model of the ensemble.

**Q: Is the severity estimate accurate?** No, and we measured that. Healthy leaves scored about 5% and the correlation with annotated lesions was about zero. The cause is that lesions are tiny and backgrounds are busy. We label it experimental. The better method would be a lesion detector trained on the dataset's boxes.

**Q: Where does the treatment advice come from? Is it reliable?** IRRI Rice Knowledge Bank and TNAU pages, listed in the app and report. It contains no doses. It has not been reviewed by an agronomist, so we tell users to confirm with their officer or KVK. For Leaf Smut we found no IRRI/TNAU page and used US extension sources, which say it is a minor disease.

**Q: Are the Kannada and Hindi translations correct?** They were written with AI help and have not been reviewed by a native speaker; both the app and the PDF say so. [[If you get them reviewed, say who did and when.]]

**Q: What if the leaf has a disease not in your six classes?** It may be mapped to the nearest class or rejected. Rejection helps but does not remove this. This is why the tool says "decision support", and why a future version should add more classes.

**Q: Why Flask and Streamlit?** Streamlit gives a quick mobile-friendly UI; Flask is a separate REST API that holds the models and logic, so the front end could be replaced without touching the model code.

**Q: Why not deploy it?** It is a local project by design. The phone camera needs HTTPS, so on a local run it works on the laptop's browser (localhost); a cloud deployment would be future work.

**Q: What did you find that surprised you?** The public dataset has the same photo under two diseases. The first EfficientNet run started with a huge loss because of its default head initialisation. The colour-based severity method did not work on real photos. Show that you tested your assumptions.

**Q: What would you do next?** Collect Karnataka field photos, train a lesion detector for severity, get the advice reviewed by agriculture officers, and add more diseases.
