# DECISIONS.md

## 1. Assumptions & open questions

**Assumed:**
- Pitch boundary moves slowly relative to frame rate (broadcast camera), so
  sampling ~2 fps (`sample_stride: 15` at 30 fps) preserves the stable crop
  while cutting decode+detect work ~15x. Verified on synthetic feed: 1800
  frames → ~120 sampled, same median polygon.
- Black frames = close-up with no pitch; plain-green frames = obscured but
  still "green everywhere" (kept as valid large polygon — matches prototype
  semantics); tiny 40x20 white outline = detection noise (filtered by
  `min_area: 1000`).
- Frame size is stable within a run; outer boundary is derived from the first
  decoded frame, not hardcoded 1280x720 (prototype bug if resolution changes).
- `mock_api` accepts any JSON on `/progress` + `/events`; strictness lives
  client-side via pydantic so malformed payloads fail before hitting the wire.
- Single-video batch job; no live-stream reconnect required.

**Would ask product/ML team:**
- What is the minimum acceptable analysis fps for crop stability? (Drives stride.)
- Is a missing boundary ever *expected* for minutes (e.g. halftime), and should
  that page an operator or just log?
- What defines "valid" beyond area — aspect, convexity, temporal consistency?
- Retention for per-frame outputs vs aggregated result? (We keep sampled
  polygons up to 10k, then drop newest — fine for minutes, not hours.)
- Auth/retries/ordering guarantees for the real reporting API?

## 2. Validation strictness vs. fallback

**Fail fast (exit 2, before any work):** missing/unparsable/invalid config,
unknown keys (`extra="forbid"`), bad `base_url`, bad `aspect_ratio`,
`sample_stride < 1`, unknown `field_detector.type`. Rationale: config errors
are deterministic — running halfway then crashing wastes a batch slot and
hides the real cause. Env overrides (`MOCK_API_URL`, `JOB_ID`, `VIDEO_PATH`)
are re-validated through the same model.

**One compat fallback:** `field_detector.type: "sam_mask_v1"` (prototype's
name) maps to `GreenThresholdDetector` instead of erroring. Rationale: it's a
rename, not a semantic error; breaking old configs adds no safety. Any other
unknown type fails fast with the list of valid values.

**Never fallback:** no silent defaults for bad values (prototype used
`.get(..., default)` everywhere — removed). No swallowing exceptions.

**Non-fatal (count + log + continue):** per-frame decode failure, detector
exception, `None`/invalid/zero-area polygon. Each increments
`invalid_count`/`read_errors` surfaced in `PipelineResult` — never silently
absorbed. Only **fatal**: video can't be opened (`VideoOpenError`) or
≥10 consecutive read failures (`StreamBrokenError`).

## 3. Performance trade-offs

- **Throughput vs accuracy:** stride 15 ≈ 15x fewer detections; per-frame cost
  (~12 ms) dominates, grab() for skipped frames is ~0.1 ms. Pitch drift in the
  synthetic feed is 2 px/frame → 30 px between samples, negligible for a crop
  box with 20 px padding. If sport has fast pans, lower stride to 5–8.
- **Sampling method:** `grab()` + conditional `retrieve()` avoids decode for
  skipped frames. Alternative `CAP_PROP_POS_FRAMES` seeks are unreliable on
  compressed mp4; grab-sequential is portable.
- **Hoisted work:** outer-boundary `Polygon`, HSV bound arrays built once.
  Prototype rebuilt the boundary polygon 1800x (≈ ms each in shapely).
- **Aggregation:** median-area polygon over sampled valid frames (robust to
  noise), not mean of valid+invalid. Memory bounded by sampled count (≤
  total/stride) + 10k cap. For hour-long feeds I'd switch to a streaming
  quantile / reservoir sample — noted as next step, not implemented.
- **Reporting overhead:** progress POST every 30 sampled frames (~4 POSTs per
  1800-frame video); synchronous with 2.0 s timeout. Fine for batch; for
  high-frequency progress I'd batch or send async.

Measured (synthetic, 300 frames, laptop): prototype ~5.2 s (all 300 decoded);
this pipeline stride 15 → ~20 sampled, ~0.6 s end-to-end (grab + detect).

## 4. AI/LLM disclosure

Used **Muse Spark (via OpenCode)** as a coding assistant during the exercise:
- Prompted for: pydantic v2 config schema sketch, grab/retrieve sampling
  pattern, project layout naming, and review of the error taxonomy.
- Wrote by hand / verified: all final code, thresholds, aggregation choice
  (median-area), exit-code contract, Docker wiring, tests, and this file.
- Every AI suggestion was read, edited, and tested locally (`pytest`, full
  pipeline run on the synthetic feed, bad-config fail-fast check) before
  keeping. No code was pasted blind.
