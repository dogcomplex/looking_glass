## Battle plan to drive BER well below 0.1

Below is a practical, product-aware plan to push BER under 0.1 using only controls we have (or can plausibly have) via vendor packs. It includes a quick inventory of tools, a prioritized set of experiments with concrete ranges and expected impacts, and specific recommendations for software tweaks to make the matrix runner more effective and reproducible.

### What we have today (quick inventory)

- Run orchestration
  - Multi-select matrix across: Trials, Seed, Window ns, Input (Digital/Cold), Path (A vs Path B analog), Path B depth, Vote3, Autotune, Sensitivity, Neighbor CT, Adaptive Input, Adaptive Max Frames, Margin mV, and Vendor Packs per component.
  - Preflight pruning and history with CSV export; variant labels show deviations from default.

- Tuning and diagnostics
  - Autotuner (with constraints and discrete choices) across comparator/TIA/clock/optics/emitter.
  - Per-component BER attribution (idealize one component).
  - Sensitivity sweeps (window/RIN/crosstalk), drift with/without re-centering, Path B sweeps (amp gain, SA I_sat), Path B analog cascade.

- Vendor packs and realistic knobs (selected highlights)
  - Emitter: power, extinction, RIN, modulation BW.
  - Optics: crosstalk (global/neighbor/diag), stray floor, SA on/I_sat, amplifier on/gain.
  - PD: responsivity, dark current, capacitance, bias.
  - TIA: discrete Rf/Cf/BW choices, input noise, output swing.
  - Comparator: vth, hysteresis, input noise, toggle rate.
  - Clock: window ns, jitter.
  - Camera: QE/read noise/bit-depth (Path A alternative); Thermal: controller traits.

### Why we’re stuck around 0.31–0.25

- With current defaults, errors are dominated by low SNR near comparator threshold (dv_mV too close to vth), non-ideal crosstalk/pedestal, and not enough “averaging” margin (temporal/spatial).
- Sensitivity on/off flips modeling bandwidth/noise but doesn’t bring net SNR over a clean decision margin by itself.
- Autotuner can find better local points, but if physical margins are thin (e.g., optics crosstalk and emitter/PD/TIA chain), we need larger knobs (window, power, CT reduction, averaging, calibration).

### Strategy: reach a clean margin first, then optimize efficiency

Work in three phases, each with explicit, physical controls. Use the matrix runner to generate tight, pruned experiments. Default to Path A with Digital input (fastest iteration), then try Cold input and Path B analog once we have a stable Path A <0.1 BER recipe.

## Phase 1 — Upper bound and bottleneck identification

- Goal: Prove the system can cross sub-0.1 BER using aggressive-yet-plausible controls, then back off.

- Experiments (matrix axes and recommended defaults)
  - Window length
    - Windows: 20, 24, 28, 32 ns
    - Expect BER monotone improvement with window; energy cost increases.
  - Emitter + optics to maximize contrast, minimize CT
    - Emitters: coherent_OBIS-850-nm_typ (low RIN, stable), thorlabs_L850P200_typ (higher power) → pick one
    - Optics: thorlabs_Engineered-Diffuser-5°_typ (lowest CT) vs 20° (baseline)
    - Expect: 5–15% absolute BER reduction vs baseline packs if CT/stray floor tightens.
  - PD + TIA bandwidth/noise pairing
    - PD: hamamatsu_S5973_typ (moderate Cj), vishay_BPW34_typ (low Cj) to favor higher BW at low noise
    - TIA: texas_instruments_OPA857EVM_typ (GHz-class) at 5k/20k settings; femto_DLPCA-200_typ for low-noise/high-gain (slower)
    - Expect: correct pairing reduces noise-driven flips; OPA857 + low Cj → sharp dv; DLPCA-200 + longer window → low-noise margin.
  - Comparator trims + per-channel calibration
    - Keep Autotune=on; run “apply calibration” behavior (we’re already computing per-channel vth suggestions; keep it enabled as a standard post step).
    - Expect: 5–10% absolute BER improvement on marginal channels.
  - Averaging/temporal voting
    - Vote3=on (default); Adaptive Input=on with MaxFrames=8..12, Margin=0.8..1.2 mV
    - Optional: Frame averaging axis (avg_frames 2–4) if needed. Expect sqrt(N) noise reduction; stops when margin met.
  - Sensitivity: off (default)
    - Keep it off for the main experiments; use only to amplify trends in sub-studies.

- Success criteria
  - See at least one configuration with p50_ber < 0.1 on Path A (Digital Input).
  - Record the best pack combo and tuned parameters.

- What to read from per-component attribution
  - If “optics_ideal_p50_ber” is still far under baseline, prioritize CT/stray/camera-like readout (or SA+amp in Path B).
  - If “comparator_ideal” or “TIA_ideal” shows big deltas, adjust TIA gain/BW and comparator vth/hysteresis ranges and rerun.

## Phase 2 — Make it practical and repeatable

- Goal: Hold sub-0.1 BER while relaxing power/time/averaging.

- Experiments
  - Window back-off
    - Once sub-0.1 is hit, reduce window by 2–4 ns steps until BER approaches threshold, then choose a conservative setting (e.g., 2 ns margin).
  - Averaging back-off
    - Reduce Adaptive MaxFrames and/or Margin mV; watch BER. Keep the minimum that sustains <0.1.
  - Power/safety guardrails
    - If we increased emitter power, step it down to a sustainable level; ensure PD/TIA not saturating (check energy proxies and “vsum_mV” if available).
  - Optional: Neighbor CT on (to de-risk)
    - Flip Neighbor CT on with modest ranges to ensure resilience; choose optics pack best under this policy.

## Phase 3 — Cold input baseline and Path B analog

- Cold input (Analog Input)
  - Goal: replicate Path A <0.1 BER with cold reader in place of digital source.
  - Expect: Slightly worse SNR; use same recipe, perhaps +2–4 ns window or +1–2 MaxFrames to reclose.

- Path B analog cascade
  - Levers: SA I_sat (lower = stronger nonlinearity), amplifier gain (balance BER vs ASE)
  - Plan: Fix best Path A optical chain; enable SA+amp; sweep:
    - SA I_sat: 0.5, 0.8, 1.0, 1.5 mW
    - Amp gain: 5, 10, 15 dB
    - Analog depth: 2–5
  - Expectation: Achieve stage-to-stage BER ≤0.1 with modest depth. If not, Path B may require telecom band pivot (1550 nm SOA/EDFA) with vendor packs we already have.

## Concrete test matrices (ready to run)

- “Upper bound first” (Path A, Digital)
  - ms-window: [20, 24, 28, 32]
  - ms-input: [digital]
  - ms-path: [path_a]
  - ms-pathb-depth: [5] (ignored by Path A)
  - ms-vote3: [1], ms-autotune: [1], ms-sensitivity: [0], ms-neighbor: [0]
  - ms-adapt-flag: [1], ms-adapt-max: [8, 12], ms-margin: [0.8, 1.0]
  - Packs:
    - emitter: [coherent_OBIS-850-nm_typ, thorlabs_L850P200_typ]
    - optics: [thorlabs_Engineered-Diffuser-5°_typ, thorlabs_Engineered-Diffuser-20°_typ]
    - sensor: [hamamatsu_S5973_typ, vishay_BPW34_typ]
    - tia: [texas_instruments_OPA857EVM_typ, femto_DLPCA-200_typ]
    - comparator: [analog_devices_LTC6752_typ]
    - clock/camera/thermal: [*_typ] (typical defaults)

- “Practicalization” (Path A, Digital)
  - Fix the best combo from above.
  - ms-window: start best, then [best−2, best−4]
  - ms-adapt-max: [best, best−2]
  - ms-margin: [best, best+0.2] to hold detection margin

- “Cold input lift”
  - ms-input: [cold]
  - Keep other settings as best from Path A; if BER >0.1, expand window/adaptive slightly.

- “Path B analog viability”
  - ms-path: [path_b_analog]
  - ms-pathb-depth: [2, 3, 4, 5]
  - optics packs as above; sweep SA I_sat/gain via autotuner constraints (or add an explicit axis later)
  - Expect a narrow sweet spot; if not reachable, recommend 1550 nm amplifier packs.

### Component-level recommendations (likely winners)

- Emitter
  - **Best bet**: coherent_OBIS-850 (low RIN, stable beam); otherwise thorlabs_L850P200 with moderate power and careful window increase.
  - **Knobs**: Increase power cautiously; extinction ≥25–30 dB; avoid excessive thermal drift.

- Optics
  - **Best bet**: thorlabs_Engineered-Diffuser-5° (low crosstalk).
  - **Keep stray floor** low; if neighbor CT needs to be modeled, tune CT neighbor/diag more negative.

- PD + TIA
  - **High-BW path**: vishay_BPW34 + OPA857EVM (5k/20k) → crisp dv at moderate windows.
  - **Low-noise path**: hamamatsu_S5973 + FEMTO DLPCA-200 → longer window but lower noise.
  - Use autotuner with discrete choices and honor pack “tuning.allowed_params” to pick supported settings.

- Comparator
  - **LTC6752** class; autotune hysteresis 0.8–2.0 mV and adjust per-channel vth after calibration for tight clustering around class means.

- Clock
  - Increase window_ns to get dv away from vth; prefer 24–32 ns for initial sub-0.1, then back off.

- Path B
  - Start 2–3 analog hops with SA I_sat≈0.8–1.0 mW and amp gain≈10 dB; minimize ASE; if not stable, consider telecom packs.

### Software tweaks to strengthen the loop

- Make “apply per-channel calibration” a distinct toggle in the Run Config (multi-select on/off) and include its result as a separate variant (so we can quantify its isolated effect).
- Add “avg_frames” as a dedicated multi-select axis (e.g., [1, 2, 4]) distinct from Vote3 and Adaptive.
- Add a “Power budget” warning layer: flag when emitter power setting + window × channels might saturate PD/TIA or exceed typical device limits.
- Expand Path B controls in UI: optional axes for SA I_sat and Amp gain (discrete lists), honoring vendor constraints.
- Enforce unit-aware constraints across packs (we’ve added skeletons; extend to PD bias and camera exposure if used).
- Add ROI or “effective channel count” control for camera mode, if we test camera-based Path A variants.

### Risks and what to watch

- Optics crosstalk floor: If attribution keeps saying optics_ideal cuts BER but real packs don’t, we may be at a structural CT floor; try the 5° diffuser or consider tighter PSF (another optics pack).
- PD/TIA mismatch: Big capacitance + ambitious BW settings → peaking/instability; pick matching PD/TIA combos, not arbitrary mixes.
- Comparator overdrive: Ensure dv_mV comfortably exceeds up-threshold+margin after calibration; otherwise vote/average/longer window.
- Path B viability: If SA+amp cannot propagate ternary with low BER for depths>2, switch to telecom band configs (EDFA/SOA), which are more mature.

### Confidence call

- **Path A (Digital)**: High likelihood to achieve p50_ber < 0.1 with the window/optics/PD+TIA/per-channel-calibration/averaging recipe. Expect getting close to 0.05 with aggressive averaging and calibration.
- **Path A (Cold input)**: Moderate likelihood; may need +2–4 ns window and slightly higher averaging to reclose < 0.1.
- **Path B analog**: Plausible at shallow depths with tuned SA/amp; deeper cascades risk ASE/noise accumulation. If C-band pivot is allowed, confidence improves.

### Concrete next steps (do this now)

- Run the “Upper bound first” matrix with the recommended packs and axes. Confirm sub-0.1 case(s).
- Freeze that best combo and run Phase 2 back-off experiments to find the minimal “sane” settings that keep <0.1.
- Replicate with Cold input. Then probe Path B analog with shallow depths and SA/amp sweeps.

If we cannot get below 0.1 on Path A after these, it likely indicates our optics CT floor, emitter RIN, or TIA/comparator noise models (or chosen packs) are too pessimistic in combination. In that case, the next move is to:
- Validate the per-component idealization and relax the limiting model (within vendor datasheet bounds), or
- Switch to a stronger optics pack (lower CT), a better PD/TIA pair, or a higher window with slightly higher power (within safety limits).