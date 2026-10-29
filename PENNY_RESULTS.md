# Penny-stocks talent pipeline: full run results

Job 46482, gnode027 (GTX 1080 Ti 11 GB), account plafnet / partition u22, model llama3.1:8b via local Ollama.
Started 2026-10-29 09:15 UTC (14:45 IST), finished 16:35 UTC (22:05 IST), 7 h 20 min, exit 0.

Outputs in `penny_results/46482/`:

- `export/scores.csv` – 100 companies ranked (score, coverage, components, flags)
- `overviews.md` / `overviews.json` – one plain-prose overview per company, written by `summarize_overviews.py`
- `dashboard.html`, `export/dashboard.json`, `export/universe.csv`
- `talent.db` (ignored by git, on the cluster only); `live/` holds the 10-minute snapshots taken while the job ran

## Website

The results are published as a GitHub Pages site built from `docs/` by `build_site.py`:
https://nishanth-nishu.github.io/glycemico-pred/ (summary and leaderboard, interactive dashboard,
all company overviews with a text filter, scores.csv). Rebuild after a new run with

```bash
python3 build_site.py penny_results/<jobid> && git add docs && git commit -m "site: job <jobid>" && git push
```

## Headline numbers

| | |
|---|---|
| Companies processed | 100 (50 India, 50 US) |
| Companies with at least one named person | 50 |
| Companies with no people (no filing text found, or stage failed) | 50 (31 India, 19 US) |
| Score band | all 100 are "weak" (< 25) by the pipeline's own thresholds |
| Going-concern flags | 24 |
| Reverse-merger flags | 9 |
| Per-company failures | 23 (see below) |

Top 10 by talent score:

| Market | Ticker | Name | Score | Coverage | People |
|---|---|---|---|---|---|
| india | URJA | Urja Global | 23.2 | 0.60 | 33 |
| india | IVC | IL&FS Investment Managers | 21.6 | 0.52 | 10 |
| india | AVROIND | Avro India | 21.5 | 0.21 | 13 |
| india | EVEXIA | Evexia Lifecare | 21.0 | 0.60 | 23 |
| india | LANDSMILL | Landsmill Green | 21.0 | 0.60 | 23 |
| us | DAVI | Davion Healthcare | 21.0 | 0.60 | 8 |
| india | STARLENT | StarlinePS Enterprises | 20.3 | 0.60 | 16 |
| india | NHCFOODS | NHC Foods | 20.2 | 0.32 | 15 |
| us | TNON | Tenon Medical | 19.6 | 0.60 | 27 |
| india | SARVESHWAR | Sarveshwar Foods | 18.8 | 0.29 | 12 |

The ranking is driven almost entirely by the momentum component (headcount / hiring / insider data); leadership is 10 or less for nearly every company and technical bench is 0 everywhere, which is what an 8B model extracting from microcap filings produces.

## Failures (23 of 100, company skipped, pipeline continued)

| Cause | Count | Companies |
|---|---|---|
| Ollama call exceeded `ollama_timeout_s` (900 s): the 8B model loops on a long filing chunk | 14 | A1L, GATECH, ASHNI, VSL, GPRO, IPDN, FTFT, BIAF, TENX, XHG, XPON, ALEC, DFDV, AMOD |
| `edgar.employee_count` int('') bug (regex matched a lone comma) | 7 | BKYI, MEDS, VSEE, VSEED, OLB, JZ, SLNH |
| DNS failure on a source fetch (unhandled, aborts the company) | 2 | SOAR, YMAT |

The int('') bug is fixed on the local `ada-fixes` branch of the clone (commit 91e5312). Each timeout costs ~15–25 min; lowering `ollama_timeout_s` to ~180 s (config/sources.yaml) would cap that at 3 min per bad chunk.

## Rerun attempts

**Job 47116 (gnode033, 29 Oct 2026 17:28-20:59 UTC / 22:58-02:29 IST): failed, nothing new scored.**
`PENNY_MODE=rerun` over the 23 skipped companies with `ollama_timeout_s: 180`, DB restored from job 46482.
Ollama ran at CPU speed on that node: 31 prompt tokens/s against 329 tokens/s on gnode027 (same GTX 1080 Ti
class), the llm-check probe took 27 s instead of under 4 s, and staging the venv, Ollama and models took 51 min
instead of seconds. Every one of the 23 companies timed out (one got "connection refused" while the server was
restarting), so `penny_results/47116/export/scores.csv` is identical to 46482's. The one useful output is
`penny_results/47116/overviews.*`: the summaries were regenerated with the corrected prompt and now read a zero
integrity penalty as "no red flags" instead of as a warning.

Fixes in `penny_run.sh` after this: it prints the driver version, dumps `ollama ps` after llm-check and exits 3
unless the model shows `100% GPU` (`PENNY_ALLOW_CPU=1` overrides), and keeps the Ollama server log as
`penny_results/<job>/ollama_serve.log` so a slow node can be diagnosed after the job is gone.

**Job 47392 (gnode027, submitted 29 Oct 2026 21:10 UTC / 02:40 IST):** same 23 companies, `ollama_timeout_s: 300`,
`-n 1 --mem-per-cpu=8G` because that node had all four GPUs free but only two CPUs. Results will land in
`penny_results/47392/`; rebuild the site from that directory when it finishes.

## Rerunning the failed companies

Inside a job with the venv and Ollama up (see `penny_run.sh`), the DB in `/scratch/nishanth.r/penny/data/talent.db` is incremental:

```bash
talent run-all --ticker us:BKYI --ticker us:MEDS ...   # fixed parser
talent export
.venv/bin/python /home2/nishanth.r/pen_sm/summarize_overviews.py --db data/talent.db --out <results dir>
```

Scratch on gnode027 is purged after ~7–10 days, so copy `penny_results/46482/talent.db` back into scratch first if the node has been cleaned.
