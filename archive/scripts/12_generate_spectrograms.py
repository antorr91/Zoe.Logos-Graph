"""
scripts/12_generate_spectrograms.py
------------------------------------
Generate spectrograms from audio files (local or downloaded from Xeno-canto)
and link them to recording_assets in the DB.

Pipeline:
  1. Read recording_assets where audio_path or audio_url exists.
  2. Download audio if only audio_url is present.
  3. Load with librosa, compute mel-spectrogram (or STFT).
  4. Save PNG to outputs/spectrograms/<recording_id>.png.
  5. Insert row in spectrograms table linking image to recording.

Usage:
    python scripts/12_generate_spectrograms.py
    python scripts/12_generate_spectrograms.py --species "Megaptera novaeangliae"
    python scripts/12_generate_spectrograms.py --limit 10

Requires:
    pip install librosa soundfile matplotlib numpy
"""

from __future__ import annotations
import argparse
import sys
import os
from pathlib import Path
from urllib.request import urlretrieve

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db_v2 import get_connection

OUT_DIR    = Path("outputs/spectrograms")
AUDIO_CACHE = Path("data/cache/audio")


def ensure_libs():
    try:
        import librosa, matplotlib, numpy, soundfile
        return librosa, matplotlib, numpy, soundfile
    except ImportError as e:
        print(f"ERROR: missing dependency: {e}")
        print("  pip install librosa soundfile matplotlib numpy")
        sys.exit(1)


def download_audio(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"    downloading {url[:60]}...")
        urlretrieve(url, str(dest))
        return True
    except Exception as e:
        print(f"    download failed: {e}")
        return False


def make_spectrogram(audio_path: Path, output_path: Path,
                     n_fft=2048, hop_length=512, n_mels=128,
                     fmax=None, title=""):
    """Generate a mel-spectrogram PNG with consistent style."""
    librosa, matplotlib, np, soundfile = ensure_libs()
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        y, sr = librosa.load(str(audio_path), sr=None, mono=True, duration=30.0)
    except Exception as e:
        print(f"    load failed: {e}")
        return None

    if len(y) < 1024:
        return None

    # Mel spectrogram
    fmax = fmax or min(sr // 2, 16000)
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=n_fft, hop_length=hop_length,
                                        n_mels=n_mels, fmax=fmax)
    S_db = librosa.power_to_db(S, ref=np.max)

    fig, ax = plt.subplots(figsize=(10, 4), dpi=120, facecolor="#0b0c0e")
    ax.set_facecolor("#0b0c0e")

    img = librosa.display.specshow(S_db, x_axis="time", y_axis="mel",
                                    sr=sr, fmax=fmax, hop_length=hop_length,
                                    cmap="magma", ax=ax)

    if title:
        ax.set_title(title, color="#e2e4ea", fontsize=11, fontfamily="serif", pad=12)
    ax.tick_params(colors="#737985", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#3e4352")
    ax.set_xlabel("time (s)", color="#737985", fontsize=9)
    ax.set_ylabel("frequency (Hz)", color="#737985", fontsize=9)

    cbar = fig.colorbar(img, ax=ax, format="%+2.0f dB", pad=0.01)
    cbar.ax.tick_params(colors="#737985", labelsize=8)
    cbar.outline.set_edgecolor("#3e4352")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(str(output_path), facecolor="#0b0c0e", bbox_inches="tight")
    plt.close(fig)

    return {
        "n_fft": n_fft, "hop_length": hop_length, "sr": sr,
        "fmax": fmax, "duration_s": len(y) / sr,
    }


def process_recording(con, rec):
    """Generate spectrogram for one recording asset."""
    rid = rec["recording_id"]
    sci = rec["species_id"]

    # Where is the audio?
    audio_file = None
    if rec["audio_path"]:
        p = Path(rec["audio_path"])
        if p.is_absolute():
            audio_file = p
        else:
            audio_file = Path(rec["audio_path"])
    elif rec["audio_url"]:
        # Download
        ext = ".mp3"
        if rec["audio_url"].endswith((".wav",".flac",".ogg")):
            ext = "." + rec["audio_url"].rsplit(".",1)[1]
        audio_file = AUDIO_CACHE / f"{rid}{ext}"
        if not download_audio(rec["audio_url"], audio_file):
            return None

    if not audio_file or not audio_file.exists():
        print(f"    no audio source for {rid}")
        return None

    out_path = OUT_DIR / f"{rid}.png"
    title = f"{rec['species_id']} — {rec.get('title','')[:50]}"
    meta = make_spectrogram(audio_file, out_path, title=title)
    if not meta:
        return None

    # Insert spectrogram record
    con.execute("""
        INSERT INTO spectrograms (recording_id, image_path, method, n_fft, hop_length, sr, fmax)
        VALUES (?, ?, 'librosa.melspectrogram', ?, ?, ?, ?)
    """, (rid, str(out_path), meta["n_fft"], meta["hop_length"], meta["sr"], meta["fmax"]))

    # Update recording duration if not set
    if not rec["duration_s"] and meta.get("duration_s"):
        con.execute("UPDATE recording_assets SET duration_s=?, sample_rate=? WHERE recording_id=?",
                   (meta["duration_s"], meta["sr"], rid))

    con.commit()
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default=None, help="Process only one species")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--regenerate", action="store_true", help="Re-generate even if exists")
    args = ap.parse_args()

    ensure_libs()
    con = get_connection()

    where = []
    params = []
    if args.species:
        sci = args.species
        sid_row = con.execute("SELECT species_id FROM species WHERE scientific_name=?", (sci,)).fetchone()
        if sid_row:
            where.append("species_id=?")
            params.append(sid_row["species_id"])

    if not args.regenerate:
        where.append("recording_id NOT IN (SELECT recording_id FROM spectrograms WHERE recording_id IS NOT NULL)")

    sql = "SELECT * FROM recording_assets"
    if where:
        sql += " WHERE " + " AND ".join(where)
    if args.limit:
        sql += f" LIMIT {args.limit}"

    rows = con.execute(sql, params).fetchall()

    if not rows:
        print("No recordings to process.")
        print("\nTo seed recordings, run:")
        print("  python scripts/03_fetch_media.py")
        print("Or import local files into recording_assets table.\n")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating spectrograms for {len(rows)} recordings...\n")
    processed = 0
    for i, rec in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {rec['recording_id']}")
        result = process_recording(con, rec)
        if result:
            print(f"    ✓ {result}")
            processed += 1

    print(f"\n✓ Generated {processed}/{len(rows)} spectrograms in {OUT_DIR}\n")


if __name__ == "__main__":
    main()
