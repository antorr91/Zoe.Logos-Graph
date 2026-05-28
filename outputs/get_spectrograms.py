"""
scripts/get_spectrograms.py
----------------------------
One-shot script: downloads audio from Xeno-canto and generates spectrograms.

Works without an API key (uses public XC API v2).
Targets birds and frogs — the species groups covered by Xeno-canto.

Steps:
  1. Queries Xeno-canto for each Aves/Amphibia species in the DB
  2. Downloads the top recording per species (mp3)
  3. Generates a mel-spectrogram PNG with librosa
  4. Saves paths to recording_assets + spectrograms tables

Usage:
    python scripts/get_spectrograms.py               # all birds + frogs
    python scripts/get_spectrograms.py --limit 10    # first 10 species only
    python scripts/get_spectrograms.py --species "Taeniopygia guttata"

Requirements:
    pip install librosa soundfile matplotlib numpy requests
"""

from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import get_connection

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

AUDIO_DIR  = Path("data/audio")
SONO_DIR   = Path("outputs/spectrograms")
NOW        = datetime.utcnow().isoformat()
XC_DELAY   = 1.2   # seconds between XC requests (be polite)


# ── Xeno-canto fetch ──────────────────────────────────────────────────────────

def xc_search(sci_name: str, max_results: int = 3) -> list[dict]:
    """Search Xeno-canto for recordings of a species."""
    try:
        url = "https://xeno-canto.org/api/2/recordings"
        params = {
            "query": f"{sci_name} q:A",   # quality A = best
            "page": 1,
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        recs = data.get("recordings", [])
        # Prefer recordings with a direct download URL and spectrogram image
        recs = [r for r in recs if r.get("file-name") or r.get("file")]
        return recs[:max_results]
    except Exception as e:
        print(f"    XC error: {e}")
        return []


def xc_download(rec: dict, dest: Path) -> bool:
    """Download a Xeno-canto recording to dest."""
    if dest.exists():
        return True
    # XC audio URL pattern
    audio_url = None
    if rec.get("file"):
        audio_url = rec["file"]
    elif rec.get("id"):
        audio_url = f"https://xeno-canto.org/{rec['id']}/download"
    if not audio_url:
        return False
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(audio_url, timeout=30, stream=True)
        if r.status_code != 200:
            return False
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return dest.stat().st_size > 10_000   # sanity check
    except Exception as e:
        print(f"    download error: {e}")
        return False


# ── Spectrogram generation ────────────────────────────────────────────────────

def make_spectrogram(audio_path: Path, out_path: Path,
                     species_name: str, rec_type: str = "") -> dict | None:
    """Generate a mel-spectrogram PNG. Returns params dict or None on failure."""
    try:
        import librosa
        import librosa.display
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("    pip install librosa soundfile matplotlib numpy")
        return None

    try:
        y, sr = librosa.load(str(audio_path), sr=None, mono=True, duration=20.0)
    except Exception as e:
        print(f"    load error: {e}")
        return None

    if len(y) < 2048:
        return None

    n_fft      = 2048
    hop_length = 512
    fmax       = min(sr // 2, 16000)
    n_mels     = 128

    S    = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=n_fft,
                                          hop_length=hop_length, n_mels=n_mels, fmax=fmax)
    S_db = librosa.power_to_db(S, ref=np.max)

    fig, ax = plt.subplots(figsize=(10, 3.5), dpi=130, facecolor="#0b0c0e")
    ax.set_facecolor("#0b0c0e")
    librosa.display.specshow(S_db, x_axis="time", y_axis="mel",
                             sr=sr, fmax=fmax, hop_length=hop_length,
                             cmap="magma", ax=ax)

    title = f"{species_name}"
    if rec_type:
        title += f" — {rec_type}"
    ax.set_title(title, color="#e2e4ea", fontsize=10, pad=8)
    ax.tick_params(colors="#737985", labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#3e4352")
    ax.set_xlabel("time (s)", color="#737985", fontsize=8)
    ax.set_ylabel("Hz", color="#737985", fontsize=8)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(pad=0.5)
    plt.savefig(str(out_path), facecolor="#0b0c0e", bbox_inches="tight")
    plt.close(fig)

    return {
        "n_fft": n_fft, "hop_length": hop_length,
        "sr": sr, "fmax": fmax, "duration_s": round(len(y) / sr, 1),
    }


# ── DB helpers ────────────────────────────────────────────────────────────────

def upsert_recording(con, rid, species_id, rec, audio_path):
    con.execute("""
        INSERT OR IGNORE INTO recording_assets
        (recording_id, species_id, title, provider, provider_id,
         url, audio_url, audio_path, license, attribution,
         recorded_by, recorded_date, location, fetched_at)
        VALUES (?, ?, ?, 'xeno-canto', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        rid, species_id,
        f"{rec.get('type','vocalisation')} (XC{rec.get('id','')})",
        str(rec.get("id", "")),
        f"https://xeno-canto.org/{rec.get('id','')}",
        f"https://xeno-canto.org/{rec.get('id','')}/download",
        str(audio_path),
        rec.get("lic", "CC BY-NC"),
        f"Xeno-canto · {rec.get('rec', 'unknown')}",
        rec.get("rec", ""),
        rec.get("date", ""),
        f"{rec.get('loc', '')}, {rec.get('cnt', '')}".strip(", "),
        NOW,
    ))
    # Update audio_path if already existed
    con.execute("UPDATE recording_assets SET audio_path=? WHERE recording_id=?",
                (str(audio_path), rid))
    con.commit()


def upsert_spectrogram(con, rid, img_path, params):
    con.execute("""
        INSERT OR REPLACE INTO spectrograms
        (recording_id, image_path, method, n_fft, hop_length, sr, fmax, generated_at)
        VALUES (?, ?, 'librosa.melspectrogram', ?, ?, ?, ?, datetime('now'))
    """, (rid, str(img_path), params["n_fft"], params["hop_length"],
          params["sr"], params["fmax"]))
    con.commit()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit",   type=int, default=None, help="Max species to process")
    ap.add_argument("--species", default=None, help="Process one species only")
    ap.add_argument("--recs-per-species", type=int, default=1,
                    help="Recordings to download per species (default 1)")
    args = ap.parse_args()

    con = get_connection()

    # Target species: birds + frogs (covered by XC)
    if args.species:
        rows = con.execute(
            "SELECT species_id, scientific_name, common_name_en FROM species "
            "WHERE scientific_name=?", (args.species,)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT species_id, scientific_name, common_name_en FROM species "
            "WHERE class_ IN ('Aves','Amphibia') ORDER BY common_name_en"
        ).fetchall()

    if args.limit:
        rows = rows[:args.limit]

    total = len(rows)
    n_downloaded = 0
    n_spectrograms = 0
    n_skipped = 0

    print(f"\n🎵 Zoe.Logos — Audio + Spectrogram pipeline")
    print(f"   Target: {total} species (Aves + Amphibia)")
    print(f"   Audio:  {AUDIO_DIR}")
    print(f"   Spectrograms: {SONO_DIR}\n")

    for i, sp in enumerate(rows, 1):
        sid  = sp["species_id"]
        sci  = sp["scientific_name"]
        name = sp["common_name_en"] or sci

        print(f"[{i:>3}/{total}] {name:35s}", end=" ", flush=True)

        # Check if we already have a spectrogram for this species
        existing = con.execute(
            "SELECT s.image_path FROM spectrograms s "
            "JOIN recording_assets r ON s.recording_id = r.recording_id "
            "WHERE r.species_id = ?", (sid,)
        ).fetchone()
        if existing:
            print(f"✓ already done ({Path(existing[0]).name})")
            n_skipped += 1
            continue

        # Search Xeno-canto
        recs = xc_search(sci, max_results=args.recs_per_species)
        if not recs:
            print("— no XC recordings")
            time.sleep(XC_DELAY)
            continue

        time.sleep(XC_DELAY)

        processed_this = 0
        for rec in recs:
            xc_id = rec.get("id", "")
            rid   = f"xc_{xc_id}"
            fname = f"{sid}_{xc_id}.mp3"
            audio_path = AUDIO_DIR / fname
            sono_path  = SONO_DIR / f"{sid}_{xc_id}.png"

            # Download audio
            ok = xc_download(rec, audio_path)
            if not ok:
                continue

            n_downloaded += 1

            # Generate spectrogram
            rec_type = rec.get("type", "")
            params = make_spectrogram(audio_path, sono_path, name, rec_type)
            if not params:
                continue

            # Save to DB
            upsert_recording(con, rid, sid, rec, audio_path)
            upsert_spectrogram(con, rid, sono_path, params)
            n_spectrograms += 1
            processed_this += 1

        if processed_this:
            print(f"✓ {processed_this} spectrogram(s)")
        else:
            print("— download failed")

    print(f"\n{'═'*55}")
    print(f"  Downloaded:    {n_downloaded} audio files")
    print(f"  Spectrograms:  {n_spectrograms} generated")
    print(f"  Skipped:       {n_skipped} (already done)")
    print(f"  Audio in:      {AUDIO_DIR}/")
    print(f"  Images in:     {SONO_DIR}/")
    print()

    if n_spectrograms > 0:
        print("✓ Now run: python scripts/07_export_web.py")
        print("  to link spectrograms into the web JSON.\n")
    else:
        print("ℹ  No new spectrograms. Check audio download or install librosa:\n")
        print("   pip install librosa soundfile matplotlib numpy\n")


if __name__ == "__main__":
    main()