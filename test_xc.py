"""
scripts/14_get_spectrograms.py
-------------------------------
Downloads audio and generates mel-spectrograms.

Sources:
  1. Xeno-canto v3 API  (birds+frogs — FREE key at xeno-canto.org/article/register)
  2. iNaturalist sounds  (no key needed)
  3. Local files in data/audio/<scientific_name>/

Setup:
    set XC_API_KEY=your-key-here
    pip install librosa soundfile matplotlib numpy requests

Usage:
    python scripts/14_get_spectrograms.py --limit 10
    python scripts/14_get_spectrograms.py --species "Turdus merula"
    python scripts/14_get_spectrograms.py
"""

from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import get_connection

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

AUDIO_DIR = Path("data/audio")
SONO_DIR  = Path("outputs/spectrograms")
NOW       = datetime.utcnow().isoformat()
DELAY     = 0.8
HEADERS   = {"User-Agent": "ZoeLogos/1.0 (research; github.com/antorr91/Zoe.Logos-Graph)"}


def xc_search_v3(sci_name, api_key, max_n=1):
    """Search XC API v3. Query must use sp: tag."""
    try:
        # v3 requires: sp:"genus species" — plain names no longer work
        genus, *rest = sci_name.split()
        epithet = rest[0] if rest else ""
        query = f'gen:{genus} sp:{epithet}' if epithet else f'sp:"{sci_name}"'
        r = requests.get("https://xeno-canto.org/api/3/recordings",
                         params={"query": query, "key": api_key, "per_page": 10},
                         headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        recs = data.get("recordings", [])
        # Sort by quality A > B > C > D > E
        quality_order = {"A":0,"B":1,"C":2,"D":3,"E":4}
        recs.sort(key=lambda x: quality_order.get(x.get("q","E"), 5))
        # Prefer recordings with direct file URL
        recs = [r for r in recs if r.get("file")]
        return recs[:max_n]
    except Exception as e:
        return []


def xc_download(rec, dest):
    if dest.exists() and dest.stat().st_size > 10_000:
        return True
    xc_id = rec.get("id","")
    # v3 returns URLs starting with // — add https:
    raw_url = rec.get("file") or f"//xeno-canto.org/{xc_id}/download"
    audio_url = ("https:" + raw_url) if raw_url.startswith("//") else raw_url
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(audio_url, headers=HEADERS, timeout=30, stream=True)
        if r.status_code != 200:
            return False
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192): f.write(chunk)
        return dest.stat().st_size > 10_000
    except Exception:
        return False


def inat_search(sci_name, max_n=1):
    try:
        r = requests.get("https://api.inaturalist.org/v1/observations",
                         params={"taxon_name": sci_name, "sounds": "true",
                                 "quality_grade": "research", "per_page": max_n},
                         headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        results = []
        for obs in r.json().get("results", []):
            for snd in obs.get("sounds", []):
                if snd.get("file_url"):
                    results.append({"id": str(obs["id"]), "url": snd["file_url"],
                                    "license": snd.get("license_code","CC BY-NC"),
                                    "attribution": obs.get("user",{}).get("login","iNat")})
        return results[:max_n]
    except Exception:
        return []


def inat_download(rec, dest):
    if dest.exists() and dest.stat().st_size > 5_000:
        return True
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(rec["url"], headers=HEADERS, timeout=30, stream=True)
        if r.status_code != 200:
            return False
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192): f.write(chunk)
        return dest.stat().st_size > 5_000
    except Exception:
        return False


def find_local(sci_name):
    folder = AUDIO_DIR / sci_name.replace(" ","_")
    if not folder.exists():
        return None
    for ext in ["*.wav","*.mp3","*.flac","*.ogg"]:
        files = list(folder.glob(ext))
        if files: return files[0]
    return None


def make_spectrogram(audio_path, out_path, title=""):
    try:
        import librosa, librosa.display, matplotlib, numpy as np
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  ✗ pip install librosa soundfile matplotlib numpy")
        return None
    try:
        y, sr = librosa.load(str(audio_path), sr=None, mono=True, duration=20.0)
    except Exception:
        return None
    if len(y) < 2048:
        return None
    n_fft, hop_length, n_mels = 2048, 512, 128
    fmax = min(sr//2, 16000)
    S    = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=n_fft,
                                           hop_length=hop_length, n_mels=n_mels, fmax=fmax)
    S_db = librosa.power_to_db(S, ref=np.max)
    fig, ax = plt.subplots(figsize=(10,3.5), dpi=120, facecolor="#0b0c0e")
    ax.set_facecolor("#0b0c0e")
    librosa.display.specshow(S_db, x_axis="time", y_axis="mel",
                             sr=sr, fmax=fmax, hop_length=hop_length, cmap="magma", ax=ax)
    ax.set_title(title, color="#e2e4ea", fontsize=10, pad=8)
    ax.tick_params(colors="#737985", labelsize=8)
    for sp in ax.spines.values(): sp.set_color("#3e4352")
    ax.set_xlabel("time (s)", color="#737985", fontsize=8)
    ax.set_ylabel("Hz",       color="#737985", fontsize=8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(pad=0.5)
    plt.savefig(str(out_path), facecolor="#0b0c0e", bbox_inches="tight")
    plt.close(fig)
    return {"n_fft":n_fft,"hop_length":hop_length,"sr":sr,"fmax":fmax,"duration_s":round(len(y)/sr,1)}


def save_db(con, rid, sid, title, provider, provider_id,
            page_url, audio_url, audio_path, license_, attr, img_path, params):
    con.execute("""INSERT OR IGNORE INTO recording_assets
        (recording_id,species_id,title,provider,provider_id,
         url,audio_url,audio_path,license,attribution,fetched_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (rid,sid,title,provider,provider_id,page_url,audio_url,str(audio_path),license_,attr,NOW))
    con.execute("UPDATE recording_assets SET audio_path=? WHERE recording_id=?",(str(audio_path),rid))
    con.execute("""INSERT OR REPLACE INTO spectrograms
        (recording_id,image_path,method,n_fft,hop_length,sr,fmax,generated_at)
        VALUES(?,?,'librosa.melspectrogram',?,?,?,?,datetime('now'))""",
        (rid,str(img_path),params["n_fft"],params["hop_length"],params["sr"],params["fmax"]))
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit",   type=int, default=None)
    ap.add_argument("--species", default=None)
    ap.add_argument("--xc-key", default=os.environ.get("XC_API_KEY",""))
    args = ap.parse_args()

    con = get_connection()
    xc_key = args.xc_key

    print("\n🎵 Zoe.Logos — Audio + Spectrogram pipeline")
    if xc_key:
        print(f"   XC API v3: ✓ (key set)")
    else:
        print("   XC API v3: NOT SET — using iNaturalist only")
        print("   Get free key: https://xeno-canto.org/article/register")
        print("   Then run:  set XC_API_KEY=your-key")

    if args.species:
        rows = con.execute(
            "SELECT species_id,scientific_name,common_name_en FROM species WHERE scientific_name=?",
            (args.species,)).fetchall()
    else:
        rows = con.execute(
            "SELECT species_id,scientific_name,common_name_en FROM species "
            "WHERE class_ IN ('Aves','Amphibia') ORDER BY common_name_en").fetchall()

    if args.limit:
        rows = rows[:args.limit]
    print(f"\n   Target: {len(rows)} species · Audio: {AUDIO_DIR} · Spectrograms: {SONO_DIR}\n")

    n_dl = n_sono = n_skip = 0

    for i, sp in enumerate(rows, 1):
        sid  = sp["species_id"]
        sci  = sp["scientific_name"]
        name = sp["common_name_en"] or sci
        print(f"[{i:>3}/{len(rows)}] {name:35s}", end=" ", flush=True)

        existing = con.execute(
            "SELECT s.image_path FROM spectrograms s "
            "JOIN recording_assets r ON s.recording_id=r.recording_id "
            "WHERE r.species_id=?", (sid,)).fetchone()
        if existing:
            print("✓ skip"); n_skip += 1; continue

        audio_path = rid = title = provider = provider_id = page_url = audio_url = license_ = attr = None

        # 1. Local file
        local = find_local(sci)
        if local:
            audio_path = local
            rid = f"local_{sid}"; title = local.stem; provider = "local"
            provider_id = local.stem; page_url = ""; audio_url = ""
            license_ = "see file"; attr = "local file"

        # 2. Xeno-canto v3
        if audio_path is None and xc_key:
            recs = xc_search_v3(sci, xc_key)
            time.sleep(DELAY)
            if recs:
                rec = recs[0]; xc_id = rec.get("id","")
                fname = AUDIO_DIR / f"xc_{xc_id}.mp3"
                if xc_download(rec, fname):
                    audio_path = fname; rid = f"xc_{xc_id}"
                    title = f"{rec.get('type','vocalisation')} (XC{xc_id})"
                    provider = "xeno-canto"; provider_id = xc_id
                    page_url = f"https://xeno-canto.org/{xc_id}"
                    audio_url = f"https://xeno-canto.org/{xc_id}/download"
                    license_ = rec.get("lic","CC BY-NC")
                    attr = f"XC · {rec.get('rec','')}"; n_dl += 1

        # 3. iNaturalist
        if audio_path is None:
            irecs = inat_search(sci)
            time.sleep(DELAY)
            if irecs:
                irec = irecs[0]; inat_id = irec["id"]
                ext = Path(irec["url"]).suffix or ".mp3"
                fname = AUDIO_DIR / f"inat_{inat_id}{ext}"
                if inat_download(irec, fname):
                    audio_path = fname; rid = f"inat_{inat_id}"
                    title = f"iNat obs {inat_id}"; provider = "inaturalist"
                    provider_id = inat_id
                    page_url = f"https://www.inaturalist.org/observations/{inat_id}"
                    audio_url = irec["url"]; license_ = irec.get("license","CC BY-NC")
                    attr = irec.get("attribution","iNaturalist"); n_dl += 1

        if audio_path is None:
            print("— no audio"); continue

        sono_path = SONO_DIR / f"{sid}.png"
        params = make_spectrogram(audio_path, sono_path, name)
        if not params:
            print("— spectrogram failed"); continue

        save_db(con, rid, sid, title, provider, provider_id,
                page_url, audio_url, audio_path, license_, attr, sono_path, params)
        n_sono += 1
        src = "XC" if "xeno" in provider else "iNat" if "inat" in provider else "local"
        print(f"✓ [{src}] {params['duration_s']}s")

    print(f"\n{'═'*55}")
    print(f"  Downloaded:   {n_dl}  |  Spectrograms: {n_sono}  |  Skipped: {n_skip}")
    if n_sono > 0:
        print(f"\n✓ Run: python scripts/07_export_web.py\n")
    elif not xc_key:
        print(f"""
No XC key — iNaturalist only mode found {n_sono} sounds.
For better coverage, get a free XC key:
  1. https://xeno-canto.org/article/register
  2. set XC_API_KEY=your-key
  3. python scripts/14_get_spectrograms.py
""")

if __name__ == "__main__":
    main()