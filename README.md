# Automated Pitch Boundary & Crop Engine — Production Pipeline

Production-ready refactor of `synthetic_field_prototype.py` (kept for reference; **do not use in production**).

## Layout

- `main.py` — thin entry point (argparse + wiring only, exit codes 0/1/2).
- `src/config.py` — validated `AppConfig` (pydantic, `extra="forbid"`). Fails fast at load.
- `src/detectors/` — `FieldDetector` Protocol + `GreenThresholdDetector` + factory.
  The **only** seam that flexes for new sports/models.
- `src/pipeline/analyzer.py` — sampled, observable pipeline; `results.py` (aggregated output), `errors.py` (fatal vs non-fatal taxonomy).
- `src/reporting/` — validated `JobProgress`/`JobEvent` wire models + `ReportingClient`.
- `src/logging_setup.py` — structured stdout logging for unattended batch runs.
- `config.example.json` — copy to `config.json` and edit.
- `tests/` — `pytest` suite (config fail-fast, detector, sampling, wire models).
- `Dockerfile` + `docker-compose.yml` — `runner` service reports to `mock_api` over HTTP.

## Quickstart (local)

```bash
pip install -r requirements.txt
cp config.example.json config.json   # edit video_path / stride as needed
python main.py --config config.json --generate-feed
# result -> output/result.json
```

Run tests:

```bash
pytest -q
```

Try bad config (fail-fast demo):

```bash
python -c "import json; c=json.load(open('config.example.json')); c['sample_stride']=0; json.dump(c, open('/tmp/bad.json','w'))"
python main.py --config /tmp/bad.json; echo "exit=$?"
# CONFIG ERROR ... exit=2, before any video work
```

## Docker + reporting

```bash
docker compose up --build
# runner -> http://mock_api:5000/api/v1/jobs/{progress,events}
# check events:
curl http://localhost:5000/api/v1/jobs/events
```

`MOCK_API_URL` / `JOB_ID` / `VIDEO_PATH` env vars override `config.json` (re-validated).
A reporting outage logs a warning and the pipeline **continues** (exit 0 if video
succeeded); a video failure reports a `failed` event best-effort and exits 1.
The two are never conflated — see `src/pipeline/errors.py`.

## Efficiency notes

- `sample_stride: 15` at 30 fps ⇒ ~2 fps analysis. Skipped frames use
  `cap.grab()` (no decode), so runtime scales with inspected frames, not file length.
- Outer-boundary polygon, HSV bounds built once, not per frame.
- Prototype's `time.sleep(0.005)` simulation removed; aggregation keeps only sampled valid
  detections (median-area polygon = stable output) plus running stats.

See `DECISIONS.md` for trade-offs, assumptions, and AI disclosure.
