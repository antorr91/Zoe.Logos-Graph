# Audio Setup Guide — Zoe.Logos-Graph

The **media tab** of each species shows acoustic recordings linked to communicative
functions. Recordings come from Xeno-Canto.

## How it works

The media tab tries three sources in order:

1. **Pre-fetched recordings** embedded in the DB (best — instant, no API, no CORS)
2. **Live Xeno-Canto API** (best-effort, may fail due to CORS / new key requirement)
3. **External links** fallback (always works — links to Xeno-Canto, Macaulay, Wikimedia)

## To embed audio permanently (recommended)

Since **Oct 2025 Xeno-Canto requires a free API key**, the cleanest approach is to
pre-fetch recordings once with `fetch_audio.py` and embed them in the HTML.

### Step 1 — Get a free Xeno-Canto key
1. Register at https://xeno-canto.org/
2. Verify your email
3. Go to your **Account page** → copy your API key

### Step 2 — Set the key
```cmd
:: Windows
set XC_API_KEY=your-key-here

:: PowerShell
$env:XC_API_KEY="your-key-here"

:: Mac/Linux
export XC_API_KEY=your-key-here
```

### Step 3 — Fetch
```cmd
:: Test on 20 species first
python fetch_audio.py --limit 20

:: All species, 6 recordings each
python fetch_audio.py

:: Birds only (best coverage), 10 recordings each
python fetch_audio.py --only-birds --per-species 10
```

This embeds recordings directly into `species_explorer.html`. After running,
the media tab loads audio instantly — no API key needed by visitors, works on
GitHub Pages, no CORS problems.

### Rate limits
Xeno-Canto allows **1000 requests/hour** — more than enough for 184 species.
The script caches responses in `data/cache/xenocanto/`, so re-runs are free.

## Without a key

If you skip the key, the media tab still works — it shows external links to
Xeno-Canto, Macaulay Library (Cornell), and Wikimedia Commons for each species.
Visitors click through to hear recordings on those sites.

## Coverage by class

| Class | Xeno-Canto coverage |
|-------|---------------------|
| Aves (birds) | Excellent — thousands of recordings |
| Mammalia | Good for bats, cetaceans, primates; sparse for others |
| Amphibia | Good for frogs |
| Insecta | Good for crickets, cicadas |
| Actinopterygii (fish) | Sparse — use external links |
| Reptilia | Sparse — use external links |

For fish/reptiles and rare mammals, the external-link fallback to Macaulay Library
gives better coverage than Xeno-Canto.
