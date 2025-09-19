Actionable Tuning Tasks (from REPORT.md feedback)

1) Confidence Intervals and Robust Stats
- Add Wilson 95% CIs for BER across all summaries (baseline, Path A, Path B TDM).
- Increase trials automatically for near-zero BER points to tighten CI.

2) Re-center Cadence & Duty
- Implement TDM re-centering cadence (every N micro-passes) and record: interval, events, duty fraction, and margin to thresholds.
- Expose CLI flags and include in JSON outputs.

3) Energy Metrics
- Report pJ/symbol (TDM-normalized) and pJ/op proxies in summaries and CSV.
- Extend scripts/summarize_tdm.py to write CSV with BER, CI, Msym/s, pJ/sym.

4) SOA/EDFA Dynamics & Noise
- Add simple SOA dynamic gain (tau, Psat) and ASE noise (NF) toggle; validate with 16-ch K=4/8 and 32-ch K=8/16 flagships.
- Add RIN/ASE interaction path in PD/TIA noise budget where appropriate.

5) TDM Realism
- Add modes for emitter-select (no switch penalties) vs EO/WSS (t_switch, isolation, IL); show throughput hit and leakage.

6) End-to-End KPIs
- Wire Path-A + TDM Path-B reporting for tokens/s vs BER and a simple MAC/s mapping.
- Produce CSV/plots for quick comparisons.

7) Stage-1 Hardening Experiment
- A/B slightly stronger nonlinearity or pre-emphasis to test if light-SA@K=8 can improve from ~0.125→~0.05 median BER.

8) Stability Dashboard
- Add per-stage slope histograms, dead-zone occupancy, min distance to thresholds (“margin”), and excursion counters.

9) BOM/Cost Hooks
- Parameterize optics tier toggles and generate a small table mapping SKU→BER/Msym/s/pJ/sym.

Notes
- Start with tasks 1–3 (quick value), then 4 & 5 (model realism), followed by 6–8 (system KPIs), and keep 9 as documentation glue.

