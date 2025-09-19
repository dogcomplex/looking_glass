MVP TDM (Path B) Hardware Outline

Scope
- Single bank: 16–32 channels ternary loop with time‑division multiplexing (TDM), 10 ns window, analog depth 5.
- Targets: 0–0.125 median BER depending on optics tier and K (active channels per frame), 5–10 Msym/s per bank.

Blocks and Requirements
- Emitter
  - Packs: tmp_lowcost_emitter_boost.yaml (1550 nm), push‑pull capable.
  - Notes: stable power per channel, modest RIN; per‑frame activation scheduling (digital) to drive K active channels.
- Optics (SA + Amp)
  - Strong‑SA option: tmp_codex_optics_medium_voa2_soa_strongsa*.yaml for K up to 8 at ~0 BER (16 ch) and viable 32 ch.
  - Light‑SA option: tmp_codex_optics_medium_voa2_lightSA.yaml for K=4 at 0 BER, K=8 around 0.125 BER.
  - Include small VOA/MZM trims per channel if available (future margin) but not mandatory for TDM K≤8.
- Sensor (PD)
  - Overlay: receiver_ingaas_typ.yaml; balanced PD sum/diff path preferred (sim: --path-b-balanced).
- TIA
  - Overlay: tia_stage_b2_low_noise.yaml; ~15 kΩ, ~55 MHz BW; low input noise; modest peaking.
- Comparator
  - Overlay: tuned_comparator.yaml; per‑channel offset trim (DAC) and small per‑channel vth trims.
  - Hysteresis small but non‑zero; input noise ≤ 0.4 mV rms class is acceptable.
- Clock
  - Overlay: clock_jitter_20ps.yaml; 10 ns base window; 20 ps rms jitter OK.
- Thermal
  - Optional pack for drift modeling; periodic re‑centering supported in software; TDM results robust at K=8 without frequent re‑trim on sim drift.

Operations Recipe (Sim‑proven)
- Auto‑zero comparator offsets at start: --path-b-calibrate-vth --path-b-calibrate-vth-scale 0.5 --path-b-calibrate-vth-passes 64
- Stage schedule (baseline): --path-b-stage-gains-db "2.0,1.0,0,-0.25,-0.25" --path-b-vth-schedule "12,12,8,6,5"
- Balanced PD and dv normalization: --path-b-balanced --normalize-dv
- TDM sparse activation and rotation:
  - --path-b-sparse-active-k K (K=4 or 8)
  - --path-b-eval-active-only (evaluate BER on active subset)
  - --path-b-sparse-rotate (cycle deterministic subsets)

Performance Map (Sim)
- 16 ch, strong‑SA: K=8 → ~10 Msym/s, 0 BER; K=4 → ~5 Msym/s, 0 BER.
- 16 ch, light‑SA: K=4 → ~5 Msym/s, 0 BER; K=8 → ~10 Msym/s, ~0.125 BER (median).
- 32 ch, strong‑SA: K=8 → ~5 Msym/s, 0 BER; K=16 → ~10 Msym/s, ~0.0625 BER.

Procurement Notes (non‑exhaustive)
- Prioritize: low‑noise TIA and comparator with offset DAC; optics SA tier per K; decent emitter power/RIN; stable 10 ns clock.
- Nice‑to‑have: small per‑channel optical trims (VOA/MZM), thermal control (TEC) on emitter/sensor.

Reproduction
- See README “TDM Path B (MVP recipe)” and scripts/run_tdm_mvp.py.

