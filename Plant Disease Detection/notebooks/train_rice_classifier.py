# %% [markdown]
# # Rice Leaf Disease Classifier: training and evaluation (Colab T4)
#
# Trains 3 models on RiceLeafDiseaseBD (6 classes): a **baseline CNN (ResNet-18)**, **EfficientNetV2-S**
# and **Swin-T**, all fine-tuned from ImageNet weights. The final model is the probability-averaged
# ensemble of EfficientNetV2-S and Swin-T.
#
# ## Before you start (on your PC)
# 1. On your PC, run `python scripts/prepare_dataset.py` (already done if `data_prepared/RiceLeaf_320.zip` exists). It creates `RiceLeaf_320.zip` (about 477 MB).
# 2. Upload it to Google Drive at `MyDrive/rice_project/data/RiceLeaf_320.zip`.
# 3. Colab: Runtime > Change runtime type > **T4 GPU**.
#
# ## Run order (so training starts as early as possible)
# Run cells top to bottom through "Training helpers". Then train in this order:
# 1. **ResNet-18 baseline** (shortest). It proves the whole pipeline, including checkpoint/resume, in minutes.
# 2. **EfficientNetV2-S**
# 3. **Swin-T**
#
# Then run the evaluation cells. You can stop after any model: each one saves to Drive when it finishes.
#
# ## Rough time estimates (NOT measured, only an estimate from typical T4 speeds)
# About 6,800 training images per epoch. Colab gives 2 CPU cores, so image augmentation is often the bottleneck (~35 s/epoch minimum).
# | Model | Input | Est. per epoch | Epochs (head + full, max) | Est. total |
# |---|---|---|---|---|
# | ResNet-18 | 224 | 35-45 s | 2 + 12 | 8-12 min |
# | EfficientNetV2-S | 288 | 70-110 s | 2 + 12 | 17-26 min |
# | Swin-T | 224 | 60-100 s | 2 + 12 | 15-23 min |
#
# The notebook prints the real seconds per epoch, so after epoch 1 you will know the true time.
#
# ## If Colab disconnects
# Reconnect, re-run all cells from the top. Splits are reloaded from Drive and each model resumes from its last
# finished epoch (`runs/<model>/last.pt`). Resuming is not bit-for-bit identical to an uninterrupted run (random
# augmentation state is not saved).
#
# ## Honest warnings
# * This dataset is from **one region and one season** (Gazipur, Bangladesh, summer 2025). Test accuracy here
#   does **not** prove it works on Karnataka fields. Take your own 20-30 phone photos and report them separately.
# * Labels are visual (expert-validated), not lab-confirmed.
# * Photos were **squashed** from 3:4 to 1:1 by the dataset authors. The app must resize to a square the same way
#   (no cropping, no padding). The evaluation transform below does exactly that.

# %%
# ---- 1. Setup ---------------------------------------------------------------------------------
import io, os, sys, json, time, math, random, hashlib, platform, subprocess, zipfile
from pathlib import Path

ON_COLAB = "google.colab" in sys.modules
SMOKE = os.environ.get("RICE_SMOKE") == "1"  # tiny local test run; never set this on Colab

if ON_COLAB:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "timm==1.0.9", "huggingface_hub<1"], check=True)
    # timm 1.0.9 needs huggingface_hub<1 (newer majors removed a name it imports)
    from google.colab import drive
    drive.mount("/content/drive")
    BASE = Path("/content/drive/MyDrive/rice_project")
    DATA_DIR = Path("/content/rice_data")  # local disk: much faster than reading images from Drive
else:
    BASE = Path(os.environ.get("RICE_BASE", "./rice_project")).resolve()
    DATA_DIR = BASE / "extracted"

DATA_ZIP = Path(os.environ.get("RICE_ZIP", BASE / "data" / "RiceLeaf_320.zip"))
OUT = BASE / "outputs"
RUNS = BASE / "runs"
EXPORT = BASE / "export"
for d in (OUT, OUT / "splits", OUT / "figures", RUNS, EXPORT):
    d.mkdir(parents=True, exist_ok=True)

import numpy as np
import pandas as pd
import matplotlib
if not ON_COLAB:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.nn.functional as F
import timm
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms as T
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from tqdm.auto import tqdm

device = "cuda" if torch.cuda.is_available() else "cpu"
print("device:", device, "|", torch.cuda.get_device_name(0) if device == "cuda" else "CPU only (training will be slow)")
print("torch", torch.__version__, "| timm", timm.__version__, "| python", platform.python_version())
print("data zip:", DATA_ZIP, "| exists:", DATA_ZIP.exists())

# %%
# ---- 2. Config, seeds, hyperparameter log -------------------------------------------------------
CFG = dict(
    seed=42,
    split_fracs=dict(train=0.70, val=0.15, test=0.15),
    # near-duplicate detection (see section 4)
    hash_size=16,              # 16x16 difference hash = 256 bits
    hash_max_bit_diff=10,      # images within 10/256 bits (~4%) are treated as near-duplicates
    burst_gap_seconds=10,      # photos of the same class taken within 10 s of each other share a group...
    burst_max_images=20,       # ...but a group of consecutive shots is capped at this many images
    # training
    batch_size=32,
    num_workers=2,
    label_smoothing=0.1,
    weight_decay=0.01,
    grad_clip=1.0,
    patience=5,                # early stopping on validation macro-F1 (full-network stage only)
    # starting values, not tuned. Stage 1 = classifier head only; stage 2 = whole network, lower LR.
    models={
        "resnet18":        dict(label="Baseline CNN (ResNet-18)", timm_name="resnet18.a1_in1k", img_size=224,
                                head_epochs=2, full_epochs=12, head_lr=1e-3, full_lr=3e-4, kwargs=dict()),
        "efficientnetv2s": dict(label="EfficientNetV2-S", timm_name="tf_efficientnetv2_s.in21k_ft_in1k", img_size=288,
                                head_epochs=2, full_epochs=12, head_lr=1e-3, full_lr=1e-4,
                                kwargs=dict(drop_rate=0.2, drop_path_rate=0.1)),
        "swin_t":          dict(label="Swin-T", timm_name="swin_tiny_patch4_window7_224.ms_in22k_ft_in1k", img_size=224,
                                head_epochs=2, full_epochs=12, head_lr=1e-3, full_lr=5e-5,
                                kwargs=dict(drop_rate=0.2, drop_path_rate=0.1)),
    },
    target_accepted_accuracy=0.95,  # rejection threshold is chosen so that accepted validation predictions reach this
    entropy_percentile=95,          # entropy limit = this percentile among CORRECT validation predictions
)
if SMOKE:  # tiny run to test the code on a laptop CPU
    CFG["batch_size"], CFG["num_workers"] = 8, 0
    for m in CFG["models"].values():
        m["head_epochs"], m["full_epochs"] = 1, 1


def seed_everything(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    torch.backends.cudnn.benchmark = False  # AMP + atomics mean runs are close to, not bit-identical, anyway


def seed_worker(_):
    s = torch.initial_seed() % 2**32
    np.random.seed(s); random.seed(s)


seed_everything(CFG["seed"])
hparams = dict(CFG, env=dict(torch=torch.__version__, timm=timm.__version__, python=platform.python_version(),
                             device=device, gpu=torch.cuda.get_device_name(0) if device == "cuda" else None))
(OUT / "hyperparameters.json").write_text(json.dumps(hparams, indent=2))
print("hyperparameters logged to", OUT / "hyperparameters.json")

# %%
# ---- 3. Load data, clean it, report class counts before/after ----------------------------------
if not (DATA_DIR / "metadata.csv").exists():
    assert DATA_ZIP.exists(), f"Upload RiceLeaf_320.zip to {DATA_ZIP} first (see README)."
    print("extracting", DATA_ZIP, "->", DATA_DIR)
    with zipfile.ZipFile(DATA_ZIP) as z:
        z.extractall(DATA_DIR)

meta = pd.read_csv(DATA_DIR / "metadata.csv", keep_default_na=False)  # columns: class,file,orig_name,capture_ts
meta["path"] = meta["class"] + "/" + meta["file"]
# format="ISO8601": the strings mix "...:58.130000" and "...:53" styles; without it pandas guesses the format from the
# first row and silently turns every row of the other style into NaT (which would disable the burst grouping).
meta["capture_ts"] = pd.to_datetime(meta["capture_ts"].replace("", pd.NA), format="ISO8601", errors="coerce")
_n_ts = int(meta["capture_ts"].notna().sum())
print(f"capture times parsed: {_n_ts}/{len(meta)}")
assert _n_ts > 0.99 * len(meta), "capture-time parsing failed; burst grouping would be silently disabled"
counts_before = meta["class"].value_counts().sort_index()

DHASH_N = CFG["hash_size"]


def dhash_bits(img):
    """Difference hash: compare each pixel with its right neighbour on a tiny grey image (bits = N*N)."""
    g = np.asarray(img.convert("L").resize((DHASH_N + 1, DHASH_N), Image.LANCZOS), dtype=np.int16)
    return np.packbits((g[:, 1:] > g[:, :-1]).flatten())  # packed uint8, N*N/8 bytes


SPLIT_CSV = OUT / "splits" / "splits.csv"
NEED_HASH = not SPLIT_CSV.exists()  # hashes are only needed when we have to (re)build the split


def inspect_file(rel):
    """Return (ok, md5, hash, hash_of_mirror_image). One pass over each file."""
    try:
        data = (DATA_DIR / rel).read_bytes()
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            im = im.convert("RGB")
        if not NEED_HASH:
            return True, hashlib.md5(data).hexdigest(), None, None
        return True, hashlib.md5(data).hexdigest(), dhash_bits(im), dhash_bits(im.transpose(Image.FLIP_LEFT_RIGHT))
    except Exception:
        return False, None, None, None


if SMOKE:
    meta = meta.groupby("class", group_keys=False).head(40).reset_index(drop=True)
    counts_before = meta["class"].value_counts().sort_index()

info = [inspect_file(p) for p in tqdm(meta["path"], desc="reading + hashing" if NEED_HASH else "checking files")]
meta["ok"] = [i[0] for i in info]
meta["md5"] = [i[1] for i in info]

# (a) unreadable files
n_bad = int((~meta["ok"]).sum())
# (b) exact byte-identical duplicates: keep the first copy; if copies carry DIFFERENT labels, drop all (label conflict)
good = meta[meta["ok"]]
dup = good.groupby("md5")["class"].agg(["nunique", "size"])
conflict_md5 = set(dup[dup["nunique"] > 1].index)
drop_conflict = good["md5"].isin(conflict_md5)
drop_dupe = good.duplicated("md5", keep="first") & ~drop_conflict
keep_mask = pd.Series(False, index=meta.index)
keep_mask[good.index[(~(drop_conflict | drop_dupe)).to_numpy()]] = True

if NEED_HASH:
    hashes = np.stack([i[2] for i, k in zip(info, keep_mask) if k])
    hashes_flip = np.stack([i[3] for i, k in zip(info, keep_mask) if k])
df = meta[keep_mask].reset_index(drop=True)
counts_after = df["class"].value_counts().sort_index()

class_names = sorted(c.replace("_", " ") for c in df["class"].unique())  # display names, alphabetical = label index order
name_to_idx = {n: i for i, n in enumerate(class_names)}
df["label"] = df["class"].str.replace("_", " ").map(name_to_idx)
NUM_CLASSES = len(class_names)

print(f"unreadable files removed: {n_bad} | exact duplicates removed: {int(drop_dupe.sum())} | label-conflict copies removed: {int(drop_conflict.sum())}")
table = pd.DataFrame({"before cleaning": counts_before, "after cleaning": counts_after}).fillna(0).astype(int)
table.loc["TOTAL"] = table.sum()
print(table)
table.to_csv(OUT / "class_counts_cleaning.csv")
(OUT / "class_names.json").write_text(json.dumps(class_names, indent=2))
print("classes (index order):", class_names)

# %%
# ---- 4. Near-duplicate groups + stratified 70/15/15 split (saved to disk, reused on re-run) ----------
if not NEED_HASH:
    splits = pd.read_csv(SPLIT_CSV)
    splits = splits[splits["path"].isin(set(df["path"]))].reset_index(drop=True)
    df = df.set_index("path").loc[splits["path"]].reset_index()
    df["split"], df["group"] = splits["split"].values, splits["group"].values
    print("loaded existing split from", SPLIT_CSV, "(delete this file to re-split)")
else:
    n = len(df)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # (a) perceptual-hash near-duplicates (also catches mirrored copies)
    POP = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)
    pairs = []
    for i in tqdm(range(n - 1), desc="near-duplicate search"):
        d = np.minimum(POP[hashes[i + 1:] ^ hashes[i]].sum(1), POP[hashes_flip[i + 1:] ^ hashes[i]].sum(1))
        for j in np.nonzero(d <= CFG["hash_max_bit_diff"])[0]:
            pairs.append((i, i + 1 + int(j), int(d[j])))
            union(i, i + 1 + int(j))

    # (b) photos of one class taken seconds apart are probably the same leaf or plant: keep them together
    for cls, sub in df.dropna(subset=["capture_ts"]).groupby("class"):
        sub = sub.sort_values("capture_ts")
        prev_idx, prev_ts, run = None, None, 0
        for idx, ts in zip(sub.index, sub["capture_ts"]):
            if prev_ts is not None and (ts - prev_ts).total_seconds() <= CFG["burst_gap_seconds"] and run < CFG["burst_max_images"]:
                union(prev_idx, idx)
                run += 1
            else:
                run = 1
            prev_idx, prev_ts = idx, ts

    df["group"] = [find(i) for i in range(n)]
    sizes = df["group"].value_counts()
    print(f"hash near-duplicate pairs found: {len(pairs)}")
    print(f"groups: {len(sizes)} | images in multi-image groups: {int(sizes[sizes > 1].sum())} | largest group: {int(sizes.max())} images")
    if sizes.max() > 0.03 * n:
        print("WARNING: a group holds >3% of all images; the split may be lopsided. Lower hash_max_bit_diff or burst_max_images.")
    cross = df.groupby("group")["class"].nunique()
    print("groups containing more than one class (possible label noise):", int((cross > 1).sum()))

    # show the pairs closest to the threshold, so you can check we are not merging different leaves
    if pairs:
        worst = sorted(pairs, key=lambda p: -p[2])[:4]
        fig, ax = plt.subplots(len(worst), 2, figsize=(5, 2.6 * len(worst)), squeeze=False)
        for r, (a, b, d_) in enumerate(worst):
            for c, k in enumerate((a, b)):
                ax[r][c].imshow(Image.open(DATA_DIR / df.loc[k, "path"])); ax[r][c].axis("off")
                ax[r][c].set_title(f"{df.loc[k, 'class']} (bit diff {d_})", fontsize=8)
        fig.suptitle("Near-duplicate pairs closest to the threshold. Different leaves here => lower the threshold")
        fig.tight_layout(); fig.savefig(OUT / "figures" / "near_duplicate_examples.png", dpi=120); plt.show()

    # stratified, group-aware 70/15/15: 20 folds of ~5% each -> 3 folds test, 3 folds val, 14 folds train
    sgkf = StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=CFG["seed"])
    fold = np.zeros(n, dtype=int)
    for k, (_, te) in enumerate(sgkf.split(df, df["label"], df["group"])):
        fold[te] = k
    df["split"] = np.where(fold < 3, "test", np.where(fold < 6, "val", "train"))
    df[["path", "class", "label", "split", "group", "orig_name", "capture_ts"]].to_csv(SPLIT_CSV, index=False)
    for s in ("train", "val", "test"):
        df.loc[df["split"] == s, ["path", "class", "label", "group"]].to_csv(OUT / "splits" / f"{s}.csv", index=False)
    print("split lists saved to", OUT / "splits")

# leakage check: no group may appear in two splits
leak = df.groupby("group")["split"].nunique()
assert (leak == 1).all(), "LEAK: a duplicate group spans several splits"
print("\nclass counts per split (no group shared between splits):")
split_table = pd.crosstab(df["class"], df["split"])[["train", "val", "test"]]
split_table.loc["TOTAL"] = split_table.sum()
print(split_table)
print("overall:", (df["split"].value_counts(normalize=True) * 100).round(1).to_dict())

train_df = df[df["split"] == "train"].reset_index(drop=True)
val_df = df[df["split"] == "val"].reset_index(drop=True)
test_df = df[df["split"] == "test"].reset_index(drop=True)

# class weights (inverse frequency, from TRAIN only) handle imbalance in the loss
cnt = np.bincount(train_df["label"], minlength=NUM_CLASSES).astype(float)
class_weights = torch.tensor(cnt.sum() / (NUM_CLASSES * cnt), dtype=torch.float32)
print("class weights:", dict(zip(class_names, class_weights.numpy().round(2))))

# %%
# ---- 5. Training helpers (augmentation, datasets, model factory, fit with resume) --------------------
class RandomIllumination:
    """Mimic uneven phone-photo lighting: a random brightness gradient + small per-channel white-balance shift."""

    def __init__(self, p=0.5, strength=0.35, wb=0.08):
        self.p, self.strength, self.wb = p, strength, wb

    def __call__(self, img):
        if random.random() > self.p:
            return img
        a = np.asarray(img, dtype=np.float32)
        h, w = a.shape[:2]
        theta = random.uniform(0, 2 * math.pi)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        ramp = (np.cos(theta) * (xx / w - 0.5) + np.sin(theta) * (yy / h - 0.5))  # -1..1 across the image
        a *= (1 + self.strength * random.uniform(-1, 1) * ramp)[..., None]
        a *= np.array([1 + random.uniform(-self.wb, self.wb) for _ in range(3)], dtype=np.float32)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def make_transforms(size, mean, std):
    train = T.Compose([
        T.RandomResizedCrop(size, scale=(0.5, 1.0), ratio=(0.8, 1.25)),
        T.RandomHorizontalFlip(), T.RandomVerticalFlip(),
        T.RandomRotation(30),
        T.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.3, hue=0.04),
        RandomIllumination(),
        T.RandomApply([T.GaussianBlur(5, sigma=(0.1, 2.0))], p=0.3),
        T.ToTensor(), T.Normalize(mean, std),
    ])
    # Eval: squash to a square (no crop/pad), the same geometry the dataset authors used.
    ev = T.Compose([T.Resize((size, size)), T.ToTensor(), T.Normalize(mean, std)])
    return train, ev


class LeafDS(Dataset):
    def __init__(self, frame, root, tfm):
        self.paths, self.labels, self.root, self.tfm = frame["path"].tolist(), frame["label"].tolist(), Path(root), tfm

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        with Image.open(self.root / self.paths[i]) as im:
            return self.tfm(im.convert("RGB")), self.labels[i]


def make_model(name, pretrained=True):
    m = CFG["models"][name]
    model = timm.create_model(m["timm_name"], pretrained=pretrained, num_classes=NUM_CLASSES, **m["kwargs"])
    # Small-weight init for the new classifier. timm's EfficientNet default (range 1/sqrt(6)) gave logits ~100x too
    # large (std 6.6) and a starting loss of ~8.8 instead of ~1.8. Harmless for the other models.
    head = model.get_classifier()
    nn.init.normal_(head.weight, std=0.01)
    nn.init.zeros_(head.bias)
    dc =timm.data.resolve_data_config({}, model=model)  # the mean/std this checkpoint was trained with
    return model, dc["mean"], dc["std"]


def make_loaders(name, mean, std):
    size = CFG["models"][name]["img_size"]
    t_train, t_eval = make_transforms(size, mean, std)
    g = torch.Generator(); g.manual_seed(CFG["seed"])
    nw = CFG["num_workers"]
    kw = dict(num_workers=nw, pin_memory=(device == "cuda"), worker_init_fn=seed_worker, persistent_workers=nw > 0)
    train_loader = DataLoader(LeafDS(train_df, DATA_DIR, t_train), CFG["batch_size"], shuffle=True, drop_last=True, generator=g, **kw)
    val_loader = DataLoader(LeafDS(val_df, DATA_DIR, t_eval), CFG["batch_size"] * 2, shuffle=False, **kw)
    return train_loader, val_loader, t_eval


def set_trainable(model, stage):
    head_ids = {id(p) for p in model.get_classifier().parameters()}
    for p in model.parameters():
        p.requires_grad = (stage == 2) or (id(p) in head_ids)


def warmup_cosine(total, warmup):
    def f(step):
        if step < warmup:
            return (step + 1) / max(1, warmup)
        return 0.5 * (1 + math.cos(math.pi * (step - warmup) / max(1, total - warmup)))
    return f


def save_atomic(obj, path):
    tmp = Path(str(path) + ".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, path)  # a disconnect mid-save can never leave a half-written checkpoint


@torch.no_grad()
def run_eval(model, loader):
    model.eval()
    logits, labels = [], []
    for x, y in loader:
        with torch.autocast(device_type=device, dtype=torch.float16, enabled=device == "cuda"):
            out = model(x.to(device, non_blocking=True))
        logits.append(out.float().cpu()); labels.append(y)
    logits, labels = torch.cat(logits), torch.cat(labels)
    loss = F.cross_entropy(logits, labels).item()
    pred = logits.argmax(1).numpy()
    return dict(loss=loss, acc=float((pred == labels.numpy()).mean()), f1=float(f1_score(labels.numpy(), pred, average="macro")),
                logits=logits.numpy(), labels=labels.numpy())


def fit(name):
    """Two-stage fine-tuning with mixed precision, label smoothing, cosine LR, grad clipping, early stopping on val macro-F1.
    Resumes automatically from runs/<name>/last.pt."""
    mc = CFG["models"][name]
    run_dir = RUNS / name
    run_dir.mkdir(exist_ok=True)
    seed_everything(CFG["seed"])
    model, mean, std = make_model(name)
    model.to(device)
    train_loader, val_loader, _ = make_loaders(name, mean, std)
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device), label_smoothing=CFG["label_smoothing"])

    st = dict(stage=1, epoch=0, best_f1=-1.0, best_epoch=-1, bad=0, history=[], done=False)  # epoch = next epoch to run in `stage`
    resume = None
    if (run_dir / "last.pt").exists():
        resume = torch.load(run_dir / "last.pt", map_location=device, weights_only=False)
        model.load_state_dict(resume["model"]); st = resume["state"]
        print(f"[{name}] resuming at stage {st['stage']}, epoch {st['epoch']}, best val F1 {st['best_f1']:.4f}")
        if st["done"]:
            print(f"[{name}] already finished. Nothing to do."); return st

    for stage in (1, 2):
        if st["stage"] > stage:
            continue
        n_ep = mc["head_epochs"] if stage == 1 else mc["full_epochs"]
        set_trainable(model, stage)
        params = [p for p in model.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=mc["head_lr"] if stage == 1 else mc["full_lr"], weight_decay=CFG["weight_decay"])
        steps = len(train_loader)
        sched = torch.optim.lr_scheduler.LambdaLR(opt, warmup_cosine(n_ep * steps, steps if stage == 2 else 0))
        scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
        if resume is not None and st["stage"] == stage and "opt" in resume:
            opt.load_state_dict(resume["opt"]); sched.load_state_dict(resume["sched"]); scaler.load_state_dict(resume["scaler"])
        resume = None
        if st["stage"] < stage:  # just moved to a new stage
            st.update(stage=stage, epoch=0, bad=0)
        print(f"[{name}] stage {stage}: {'head only' if stage == 1 else 'full network'}, {n_ep} epochs, trainable params {sum(p.numel() for p in params):,}")

        for epoch in range(st["epoch"], n_ep):
            t0 = time.time()
            model.train() if stage == 2 else model.eval()  # stage 1: frozen backbone keeps its BatchNorm/dropout behaviour fixed
            run_loss, seen = 0.0, 0
            for x, y in tqdm(train_loader, desc=f"{name} s{stage} e{epoch + 1}/{n_ep}", leave=False):
                x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
                opt.zero_grad(set_to_none=True)
                with torch.autocast(device_type=device, dtype=torch.float16, enabled=device == "cuda"):
                    loss = criterion(model(x), y)
                scaler.scale(loss).backward()
                scaler.unscale_(opt)
                nn.utils.clip_grad_norm_(params, CFG["grad_clip"])
                scaler.step(opt); scaler.update(); sched.step()
                run_loss += loss.item() * len(y); seen += len(y)
            ev = run_eval(model, val_loader)
            rec = dict(stage=stage, epoch=epoch + 1, train_loss=run_loss / seen, val_loss=ev["loss"], val_acc=ev["acc"],
                       val_f1=ev["f1"], lr=opt.param_groups[0]["lr"], seconds=round(time.time() - t0, 1))
            st["history"].append(rec)
            improved = ev["f1"] > st["best_f1"] + 1e-4
            if improved:
                st.update(best_f1=ev["f1"], best_epoch=len(st["history"]), bad=0)
                save_atomic(dict(model=model.state_dict(), val_f1=ev["f1"], name=name), run_dir / "best.pt")
            elif stage == 2:
                st["bad"] += 1
            st["epoch"] = epoch + 1
            print(f"[{name}] s{stage} e{epoch + 1}/{n_ep}  train loss {rec['train_loss']:.4f} | val loss {rec['val_loss']:.4f} "
                  f"acc {rec['val_acc']:.4f} F1 {rec['val_f1']:.4f} | {rec['seconds']}s {'*best*' if improved else ''}")
            stop = stage == 2 and st["bad"] >= CFG["patience"]
            if stage == 2 and (stop or epoch + 1 == n_ep):
                st["done"] = True
            save_atomic(dict(model=model.state_dict(), opt=opt.state_dict(), sched=sched.state_dict(), scaler=scaler.state_dict(), state=st),
                        run_dir / "last.pt")
            (run_dir / "history.json").write_text(json.dumps(st["history"], indent=2))
            if stop:
                print(f"[{name}] early stopping: no val F1 gain for {CFG['patience']} epochs"); break
        if stage == 1:
            st.update(stage=2, epoch=0, bad=0)
    st["done"] = True
    save_atomic(dict(model=model.state_dict(), state=st), run_dir / "last.pt")
    print(f"[{name}] finished. best val F1 {st['best_f1']:.4f} at overall epoch {st['best_epoch']}")
    del model
    if device == "cuda":
        torch.cuda.empty_cache()
    return st


# %% [markdown]
# ## 6-8. Train the models
# Run **in this order**. Each cell can be re-run after a disconnect and continues where it stopped.
# Watch the first epoch's seconds to get the true time per model.

# %%
# ---- 6. Train baseline CNN (ResNet-18): shortest, validates the whole pipeline ----------------------
fit("resnet18")

# %%
# ---- 7. Train EfficientNetV2-S -----------------------------------------------------------------------
fit("efficientnetv2s")

# %%
# ---- 8. Train Swin-T ---------------------------------------------------------------------------------
fit("swin_t")

# %% [markdown]
# ## 9. Evaluation: TEST split only
# Validation data is used for (a) early stopping, (b) fitting the temperature, (c) choosing the rejection threshold.
# The test split is used once, here, for the final numbers.

# %%
# ---- 9a. Logits of every trained model on val and test (cached to Drive) ------------------------------
def load_best(name):
    model, mean, std = make_model(name, pretrained=False)
    ck = torch.load(RUNS / name / "best.pt", map_location="cpu", weights_only=False)
    model.load_state_dict(ck["model"])
    return model.to(device).eval(), mean, std


@torch.no_grad()
def logits_for(name, frame, root=DATA_DIR):
    model, mean, std = load_best(name)
    _, t_eval = make_transforms(CFG["models"][name]["img_size"], mean, std)
    dl = DataLoader(LeafDS(frame, root, t_eval), CFG["batch_size"] * 2, shuffle=False, num_workers=CFG["num_workers"])
    out = []
    for x, _ in dl:
        with torch.autocast(device_type=device, dtype=torch.float16, enabled=device == "cuda"):
            out.append(model(x.to(device)).float().cpu())
    del model
    return torch.cat(out).numpy()


trained = [n for n in CFG["models"] if (RUNS / n / "best.pt").exists()]
print("models available:", trained)
# NOTE: logits are cached. If you retrain a model, delete outputs/logits_<model>_*.npy so they are recomputed.
LOGITS = {}
for n in trained:
    for split, frame in (("val", val_df), ("test", test_df)):
        f = OUT / f"logits_{n}_{split}.npy"
        if not f.exists():
            np.save(f, logits_for(n, frame))
        LOGITS[(n, split)] = np.load(f)
y_val, y_test = val_df["label"].to_numpy(), test_df["label"].to_numpy()

# %%
# ---- 9b. Temperature scaling (fit on VAL), calibration quality (ECE), reliability diagrams -----------
def softmax(z, T=1.0):
    z = z / T
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def fit_temperature(logits, labels):
    z, y = torch.tensor(logits), torch.tensor(labels)
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=200)

    def closure():
        opt.zero_grad()
        loss = F.cross_entropy(z / log_t.exp(), y)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp())


def ece_score(probs, labels, n_bins=15):
    conf, pred = probs.max(1), probs.argmax(1)
    correct = pred == labels
    e = 0.0
    edges = np.linspace(0, 1, n_bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            e += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(e)


def reliability(ax, probs, labels, title, n_bins=10):
    conf, correct = probs.max(1), probs.argmax(1) == labels
    edges = np.linspace(0, 1, n_bins + 1)
    xs, ys = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.sum() >= 3:
            xs.append(conf[m].mean()); ys.append(correct[m].mean())
    ax.plot([0, 1], [0, 1], "k--", lw=1); ax.plot(xs, ys, "o-")
    ax.set_title(f"{title}\nECE {ece_score(probs, labels):.3f}", fontsize=9); ax.set_xlabel("confidence"); ax.set_ylabel("accuracy")


TEMP, P_VAL, P_TEST = {}, {}, {}
fig, axes = plt.subplots(len(trained), 2, figsize=(7, 3.4 * len(trained)), squeeze=False)
for r, n in enumerate(trained):
    TEMP[n] = fit_temperature(LOGITS[(n, "val")], y_val)
    P_VAL[n] = softmax(LOGITS[(n, "val")], TEMP[n]); P_TEST[n] = softmax(LOGITS[(n, "test")], TEMP[n])
    reliability(axes[r][0], softmax(LOGITS[(n, "test")]), y_test, f"{CFG['models'][n]['label']} - before")
    reliability(axes[r][1], P_TEST[n], y_test, f"{CFG['models'][n]['label']} - after T={TEMP[n]:.2f}")
fig.tight_layout(); fig.savefig(OUT / "figures" / "reliability_diagrams.png", dpi=130); plt.show()

ENS = [n for n in ("efficientnetv2s", "swin_t") if n in trained]
if len(ENS) == 2:  # ensemble = mean of the two temperature-scaled probability vectors
    P_VAL["ensemble"] = np.mean([P_VAL[n] for n in ENS], axis=0)
    P_TEST["ensemble"] = np.mean([P_TEST[n] for n in ENS], axis=0)
    raw_ens = np.mean([softmax(LOGITS[(n, "test")]) for n in ENS], axis=0)
    print(f"Ensemble ECE (test): uncalibrated {ece_score(raw_ens, y_test):.4f} -> calibrated {ece_score(P_TEST['ensemble'], y_test):.4f}")
else:
    print("Train both EfficientNetV2-S and Swin-T to get the ensemble.")
print("temperatures:", {k: round(v, 3) for k, v in TEMP.items()})

# %%
# ---- 9c. Metrics, parameter count, model size, CPU latency, comparison table ---------------------------
def cpu_ms_per_image(name, runs=30):
    model, _, _ = make_model(name, pretrained=False)
    model.eval()
    torch.set_num_threads(2)  # a free Hugging Face Space has 2 vCPUs
    s = CFG["models"][name]["img_size"]
    x = torch.randn(1, 3, s, s)
    with torch.no_grad():
        for _ in range(3):
            model(x)
        ts = []
        for _ in range(3 if SMOKE else runs):
            t0 = time.perf_counter(); model(x); ts.append((time.perf_counter() - t0) * 1000)
    return float(np.median(ts))


def model_stats(name):
    model, _, _ = make_model(name, pretrained=False)
    buf = io.BytesIO(); torch.save(model.state_dict(), buf)
    return sum(p.numel() for p in model.parameters()) / 1e6, buf.tell() / 1024 / 1024


def metrics(probs, labels):
    pred = probs.argmax(1)
    rep = classification_report(labels, pred, target_names=class_names, output_dict=True, zero_division=0)
    return dict(accuracy=float((pred == labels).mean()), macro_precision=rep["macro avg"]["precision"],
                macro_recall=rep["macro avg"]["recall"], macro_f1=rep["macro avg"]["f1-score"], per_class={c: rep[c] for c in class_names})


STATS = {n: (*model_stats(n), cpu_ms_per_image(n)) for n in trained}
rows, RESULTS = [], {}
for key in trained + (["ensemble"] if "ensemble" in P_TEST else []):
    m = metrics(P_TEST[key], y_test)
    RESULTS[key] = m
    if key == "ensemble":
        params, size, ms = (sum(STATS[n][i] for n in ENS) for i in range(3))
        ece_raw, ece_cal, label, temp = ece_score(raw_ens, y_test), ece_score(P_TEST[key], y_test), "Ensemble (EffNetV2-S + Swin-T)", "-"
    else:
        params, size, ms = STATS[key]
        ece_raw, ece_cal, label, temp = ece_score(softmax(LOGITS[(key, "test")]), y_test), ece_score(P_TEST[key], y_test), CFG["models"][key]["label"], f"{TEMP[key]:.2f}"
    rows.append({"Model": label, "Accuracy": m["accuracy"], "Macro P": m["macro_precision"], "Macro R": m["macro_recall"], "Macro F1": m["macro_f1"],
                 "Params (M)": params, "Size (MB, fp32)": size, "CPU ms/img (2 threads)": ms, "ECE before": ece_raw, "ECE after": ece_cal, "T": temp})
comparison = pd.DataFrame(rows)
print(comparison.round(4).to_string(index=False))
comparison.to_csv(OUT / "comparison_table.csv", index=False)
(OUT / "comparison_table.txt").write_text(comparison.round(4).to_string(index=False))
(OUT / "test_metrics.json").write_text(json.dumps(RESULTS, indent=2, default=float))  # sklearn returns numpy ints for 'support'
print("\nCPU latency is measured on THIS machine (Colab CPU). Re-measure on the deployed Space before quoting it.")

best_key = "ensemble" if "ensemble" in P_TEST else trained[-1]
print(f"\nPer-class results, {best_key} (test):")
print(pd.DataFrame(RESULTS[best_key]["per_class"]).T[["precision", "recall", "f1-score", "support"]].round(3))

# %%
# ---- 9d. Confusion matrices and training curves ------------------------------------------------------
keys = trained + (["ensemble"] if "ensemble" in P_TEST else [])
fig, axes = plt.subplots(1, len(keys), figsize=(5.2 * len(keys), 5), squeeze=False)
for ax, k in zip(axes[0], keys):
    cm = confusion_matrix(y_test, P_TEST[k].argmax(1), labels=list(range(NUM_CLASSES)))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(NUM_CLASSES)); ax.set_yticks(range(NUM_CLASSES))
    ax.set_xticklabels(class_names, rotation=45, ha="right", fontsize=8); ax.set_yticklabels(class_names, fontsize=8)
    for i in range(NUM_CLASSES):
        for j in range(NUM_CLASSES):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=8)
    ax.set_title(CFG["models"][k]["label"] if k in CFG["models"] else "Ensemble", fontsize=10); ax.set_xlabel("predicted"); ax.set_ylabel("true")
fig.tight_layout(); fig.savefig(OUT / "figures" / "confusion_matrices.png", dpi=130); plt.show()

fig, axes = plt.subplots(1, 3, figsize=(15, 3.8))
for n in trained:
    h = pd.DataFrame(json.loads((RUNS / n / "history.json").read_text()))
    x = np.arange(1, len(h) + 1)
    axes[0].plot(x, h["train_loss"], label=n); axes[1].plot(x, h["val_loss"], label=n); axes[2].plot(x, h["val_f1"], label=n)
for ax, t in zip(axes, ("train loss", "validation loss", "validation macro-F1")):
    ax.set_title(t); ax.set_xlabel("epoch (stage 1 then stage 2)"); ax.legend()
fig.tight_layout(); fig.savefig(OUT / "figures" / "training_curves.png", dpi=130); plt.show()

# %%
# ---- 10. Rejection thresholds, chosen on VALIDATION data only -------------------------------------------
final = "ensemble" if "ensemble" in P_VAL else trained[-1]
pv = P_VAL[final]
conf_v, correct_v = pv.max(1), pv.argmax(1) == y_val


def norm_entropy(p):
    return -(p * np.log(p + 1e-12)).sum(1) / np.log(p.shape[1])


ent_v = norm_entropy(pv)

# Risk-coverage: for every candidate threshold, accuracy among the predictions we would accept.
order = np.argsort(-conf_v)
cum_acc = np.cumsum(correct_v[order]) / np.arange(1, len(order) + 1)
cov = np.arange(1, len(order) + 1) / len(order)
ok = np.nonzero((cum_acc >= CFG["target_accepted_accuracy"]) & (cov >= 0.5))[0]
if len(ok):
    conf_thr = float(max(conf_v[order][ok.max()], 0.5))  # lowest confidence that still meets the target (largest coverage)
else:
    conf_thr = float(np.quantile(conf_v, 0.2))
    print("WARNING: target accepted accuracy not reachable on validation data; fell back to the 20th confidence percentile.")
ent_thr = float(np.percentile(ent_v[correct_v], CFG["entropy_percentile"])) if correct_v.any() else 1.0


def decide(p):
    reject = (p.max(1) < conf_thr) | (norm_entropy(p) > ent_thr)
    return reject


rv = decide(pv)
print(f"Chosen on validation: confidence >= {conf_thr:.3f} and normalised entropy <= {ent_thr:.3f}")
print(f"  validation: coverage {(~rv).mean():.1%}, accuracy on accepted {correct_v[~rv].mean():.1%}, overall accuracy {correct_v.mean():.1%}")

pt = P_TEST[final]
rt, correct_t = decide(pt), pt.argmax(1) == y_test
print(f"  TEST      : coverage {(~rt).mean():.1%}, accuracy on accepted {correct_t[~rt].mean():.1%}, "
      f"errors caught by rejection {rt[~correct_t].mean() if (~correct_t).any() else float('nan'):.1%}")

fig, ax = plt.subplots(figsize=(4.5, 3.5))
ax.plot(cov, cum_acc); ax.axhline(CFG["target_accepted_accuracy"], ls="--", c="grey"); ax.axvline((~rv).mean(), ls=":", c="red")
ax.set_xlabel("coverage (fraction accepted)"); ax.set_ylabel("accuracy on accepted"); ax.set_title("Risk-coverage (validation)")
fig.tight_layout(); fig.savefig(OUT / "figures" / "risk_coverage.png", dpi=130); plt.show()

# Optional: put non-rice photos (other plants, hands, soil, random objects) in MyDrive/rice_project/data/non_rice_samples/
# to measure how many are rejected. These are NOT used to choose the threshold.
OOD_DIR = BASE / "data" / "non_rice_samples"
if OOD_DIR.exists() and len(ENS) == 2:
    files = [p for p in OOD_DIR.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    if files:
        ood = pd.DataFrame({"path": [p.name for p in files], "label": 0})
        po = np.mean([softmax(logits_for(n, ood, OOD_DIR), TEMP[n]) for n in ENS], axis=0)
        print(f"Non-rice samples: {len(files)} | rejected: {decide(po).mean():.1%} (higher is better)")

# %%
# ---- 11. Error analysis: most confused class pairs and misclassified examples -----------------------------
pred_t = pt.argmax(1)
cm = confusion_matrix(y_test, pred_t, labels=list(range(NUM_CLASSES)))
pairs_err = sorted(((cm[i, j], class_names[i], class_names[j]) for i in range(NUM_CLASSES) for j in range(NUM_CLASSES) if i != j and cm[i, j] > 0), reverse=True)
print("Most common confusions (count, true -> predicted):")
for c, a, b in pairs_err[:6]:
    print(f"  {c:3d}  {a}  ->  {b}")

wrong = np.nonzero(pred_t != y_test)[0]
wrong = wrong[np.argsort(-pt.max(1)[wrong])][:8]  # the most CONFIDENT mistakes are the most informative
if len(wrong):
    fig, axes = plt.subplots(2, 4, figsize=(14, 7.5))
    for ax in axes.flat:
        ax.axis("off")
    for ax, i in zip(axes.flat, wrong):
        ax.imshow(Image.open(DATA_DIR / test_df.loc[i, "path"]))
        ax.set_title(f"true: {class_names[y_test[i]]}\npred: {class_names[pred_t[i]]} ({pt[i].max():.2f})", fontsize=9)
    fig.tight_layout(); fig.savefig(OUT / "figures" / "misclassified_examples.png", dpi=120); plt.show()

# %% [markdown]
# ### Error-analysis notes (WRITE THESE YOURSELF after looking at the figure above)
# Do not copy generic reasons. Look at the confused pairs and the misclassified images, then fill in:
# * Confused pair 1: `____ -> ____`, count `__`. What the images show: `____`.
# * Hypotheses worth checking (NOT verified results): Brown Spot and Blast both produce small brown lesions, so early-stage
#   photos can look alike; Tungro causes yellow-orange discolouration that can resemble nutrient deficiency or senescence;
#   Sheath Blight lesions are on the sheath, so a leaf-only photo may lack the key sign.
# * Is the mistake a label-noise problem (the image truly looks like the predicted class)? `____`

# %%
# ---- 12. Export for the app (copy these to the project's models/ folder) ------------------------------------
import shutil

(EXPORT / "class_names.json").write_text(json.dumps(class_names, indent=2))
export_models = {}
for n, fname in (("efficientnetv2s", "efficientnetv2s.pt"), ("swin_t", "swin_t.pt"), ("resnet18", "baseline_resnet18.pt")):
    if (RUNS / n / "best.pt").exists():
        model, mean, std = load_best(n)
        torch.save(model.cpu().state_dict(), EXPORT / fname)  # plain fp32 weights; the app rebuilds the model with timm
        export_models[n] = dict(file=fname, timm_name=CFG["models"][n]["timm_name"], img_size=CFG["models"][n]["img_size"],
                                mean=list(mean), std=list(std), temperature=TEMP.get(n), kwargs=CFG["models"][n]["kwargs"])
calibration = dict(
    class_names=class_names, models=export_models, ensemble=ENS,
    ensemble_rule="mean of the temperature-scaled softmax probabilities of the listed models",
    reject=dict(min_confidence=conf_thr, max_normalised_entropy=ent_thr, chosen_on="validation split",
                target_accepted_accuracy=CFG["target_accepted_accuracy"], entropy_percentile=CFG["entropy_percentile"]),
    preprocessing="resize image to a SQUARE of img_size (no crop, no padding), RGB, normalise with mean/std",
)
(EXPORT / "calibration.json").write_text(json.dumps(calibration, indent=2))
for f in ("hyperparameters.json", "comparison_table.csv", "test_metrics.json", "class_counts_cleaning.csv"):
    if (OUT / f).exists():
        shutil.copy(OUT / f, EXPORT / f)
print("exported to", EXPORT)
for p in sorted(EXPORT.iterdir()):
    print(f"  {p.name:28s} {p.stat().st_size / 1e6:8.1f} MB")
if ON_COLAB:
    print("\nDownload the 4 required files from this Drive folder and put them in the project's models/ folder:"
          "\n  class_names.json, efficientnetv2s.pt, swin_t.pt, calibration.json")

# %% [markdown]
# ## 13. Results for your report: PASTE YOUR REAL NUMBERS HERE (no values are invented in this notebook)
# Copy from `outputs/comparison_table.csv`, `outputs/test_metrics.json` and the figures in `outputs/figures/`.
#
# | Model | Accuracy | Macro F1 | Params (M) | Size (MB) | CPU ms/img | ECE after T-scaling |
# |---|---|---|---|---|---|---|
# | Baseline CNN (ResNet-18) | ___ | ___ | ___ | ___ | ___ | ___ |
# | EfficientNetV2-S | ___ | ___ | ___ | ___ | ___ | ___ |
# | Swin-T | ___ | ___ | ___ | ___ | ___ | ___ |
# | Ensemble | ___ | ___ | ___ | ___ | ___ | ___ |
#
# Remember: these are numbers on the **dataset's own test split** (same region and season as training).
# Real-world accuracy on your own phone photos is reported separately in Stage 6.
