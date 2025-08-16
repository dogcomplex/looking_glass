# Looking Glass — System Design Document (DESIGN.md)
**Version:** 0.1 (scaffold)  
**Updated:** 2025-08-16 06:05 UTC  
**Codebase:** `LookingGlassSim` (see `README.md` for quick start)  
**Project Codename:** *Looking Glass*

---

## 0) Executive Summary

Looking Glass is a staged, hybrid analog–digital **optical AI co‑processor** focused on **Transformer feature extraction** with **ternary weights**. It targets two complementary embodiments:

- **Path A (Camera/DMD loop):** Commodity camera + DLP/SLM drives a free‑space optical reservoir (glass/crystal) for linear ops; digital performs threshold and nonlinearity. Maximizes *practicality* and iteration speed.
- **Path B (Analog ternary loop):** All‑optical linear block + **saturable absorption (threshold)** + **optical amplification** to propagate a ternary state between layers. Camera used **only** for final readout. Maximizes *speed/energy* and reduces O‑E‑O penalties.

Both paths share identical software orchestration and can be validated in sim before hardware. The endgame is a **Mixture‑of‑Experts (MoE)** optical accelerator: many small, isolated optical “experts” (glass cubes / crystals) compute in parallel—fitting attention heads / experts—coordinated by a digital host. An **optical delay line** (fiber spool) provides a cheap KV‑cache / context memory. Upgrades introduce **WDM/angular multiplexing** (multiple colors/angles addressing many weights per volume).

This document consolidates requirements, architecture, risks, validation, and upgrade paths; it maps explicitly to the runnable scaffold in `looking_glass/` and defines how to extend simulation components into product‑grade models and hardware drivers.

---

## 1) Goals & Non‑Goals

### 1.1 Goals
- **G1 — Demonstrate feasibility** of optical ternary feature extraction for Transformers (single attention block first).
- **G2 — MoE scalability:** Parallel “experts” with minimal crosstalk; shared DLP/camera or analog loop.
- **G3 — Shared software:** One orchestrator for sim → bench → workstation; parameter packs select specific gear.
- **G4 — De‑risk with sims:** Credible physics‑informed simulation spanning optimistic/typical/pessimistic bounds.
- **G5 — Investor‑grade proof:** Public demos showing: BER vs throughput, energy/token, stability over time, and speedups vs GPU on selected kernels.
- **G6 — Upgrade continuity:** Components reusable from <$1k PoC → $5–10k prosumer → lab‑grade.

### 1.2 Non‑Goals (for v0.x)
- Training full‑scale models purely optically.  
- Custom PIC tape‑out.  
- Perfect absolute accuracy; focus on **ternary robustness** and error‑tolerant readout.  

---

## 2) System Concept

### 2.1 Computational Kernel
We implement the feature extraction of attention heads (e.g., sign(Wx)) in optics:
- Encode ternary/vector input (Query/Key/Value projection slices).
- Free‑space multiply via **structured scattering** (diffractive masks / glass reservoir).
- Read intensity or interfere with a reference (optional phase readout).
- Apply **threshold** to obtain ternary outputs.  
- Feed to next layer or accumulate digitally.

### 2.2 Two Primary Loops
- **Path A — Camera/DMD Loop:**  
  Laser → DLP/SLM (encodes vector/frame) → optical reservoir (glass/crystal) → camera (intensity) → digital threshold/ReLU → next frame to DLP.  
  *Pros:* Off‑the‑shelf, simple, transparent debugging.  
  *Cons:* Limited by camera/DLP frame rate; O‑E‑O latency/energy.

- **Path B — Analog Ternary Loop:**  
  Laser(s) → diffractive/holographic weight → saturable absorber (threshold) → optical amplifier → (optionally passive routing) → next diffractive stage. Final camera readout only.  
  *Pros:* Picosecond‑class stage latency, low energy, minimal O‑E‑O.  
  *Cons:* More alignment/control; component sourcing (SOA/EDFA, SA), stability.

Both share common submodules: emitters, optics PSF/crosstalk, photodetectors (final read), TIAs/comparators (Path A), clocking, thermal drift, mitigation toggles.

---

## 3) Architecture & Dataflow

### 3.1 High‑Level Diagram (both paths)

```
           ┌───────────┐     ┌──────────────┐     ┌─────────────┐
Input x →  │ Orchestr. │ →→  │  Emitter     │ →→  │   Optics     │
           │  (Host)   │     │(Laser/DLP/…) │     │ (Reservoir)  │
           └────┬──────┘     └──────┬───────┘     └──────┬──────┘
                │                   │                    │
             control             wavefront            scattered
                │                   │                    │
         (Path A) ──────────────── Camera ──→ TIA/Comp ──→ Ternary y
                                      │                   │
                                      └──── Host loop ◄───┘

         (Path B) ── Saturable Absorber ─→ Optical Amp ─→ Next Stage → … → Final Camera
```

### 3.2 MoE Topology
- Partition sensor and DLP “canvas” into **tiles**; each tile illuminates an **isolated glass cube** (expert).  
- Outputs multiplexed spatially to a single camera (global shutter).  
- Host routes token workload across experts (load‑balanced).  
- Fiber spool delay optionally provides shared KV‑cache or temporal mixing.

### 3.3 Timing/Coherence
- Pulse width & path spread **< coherence time**; global shutter snapshots the interference before decoherence.  
- For Path A, the **frame exposure** and **global shutter** ensure single‑shot consistency; multiple small cameras are avoided for phase/timing misalignment.  
- For Path B, **per‑stage optical length** kept below decoherence; amplifier + SA reset the dynamic range each hop.

---

## 4) Components (Abstract + Mapping to `LookingGlassSim`)

Each block has a simulation counterpart with parameters and noise sources. Real vendors are integrated via **parameter packs**.

### 4.1 Emitters (`sim/emitter.py`)
- **Abstract:** CW or pulsed diode/VCSEL array; optionally AOM/EOM. Supports extinction ratio, RIN, temperature coefficients, finite rise/fall.
- **Key Params:** `power_mw_per_ch`, `extinction_db`, `rin_dbhz`, `rise_fall_ns_10_90`, `temp_coeff_pct_per_C`.
- **Path A:** Single‑mode laser + DLP/SLM to encode frames.  
- **Path B:** Single‑/multi‑wavelength sources; AOM for ternary gating; WDM lasers for multiplexing.

### 4.2 Optics/Reservoir (`sim/optics.py`)
- **Abstract:** Structured scattering with PSF blur, crosstalk, stray floor, contrast asymmetry; optional **SOA/EDFA** and **saturable absorber**.
- **Key Params:** `psf_kernel`, `crosstalk_db`, `stray_floor_db`, `amp_on/gain_db`, `sat_abs_on`, `sat_I_sat`, `sat_alpha`.
- **Embodiments:** Decorative glass cubes → photorefractive crystals → 3D laser‑written phase plates; later, **WDM/angular multiplexed** holograms.

### 4.3 Sensors (`sim/sensor.py`), TIAs (`sim/tia.py`), Comparators (`sim/comparator.py`) — Path A
- **Photodiode:** Responsivity, dark current, shot noise (Poisson), junction capacitance.
- **TIA:** Transimpedance, input‑referred noise, bandwidth, simple LPF dynamics.
- **Comparator:** Threshold, hysteresis, input noise, temp drift.
- **Outcome:** Ternary symbol per channel per frame; BER tracked vs “truth”.

### 4.4 Clock (`sim/clock.py`)
- Exposure/window length and **timing jitter**. Controls energy/throughput tradeoff.

### 4.5 Mitigations (`sim/mitigations.py` placeholder)
- Software flags for: iris/aperture, baffles, TEC thermal stabilization, clean‑room multiplier, EMI shielding, mechanical isolation; each reduces specific noise/drift terms.

---

## 5) Simulation Scope & KPIs

### 5.1 Core KPIs
- **BER** (bit error rate) per stage and end‑to‑end.  
- **Energy/token** (pJ/token for sub‑ops).  
- **Throughput** (tokens/s; or frames/s × channels).  
- **SNR margins** vs parameter drift (temp, aging).  
- **Stability** (BER drift over hours).  
- **Crosstalk index** (Δoutput when neighbor toggles).

### 5.2 Scenarios
- **Smoke:** `configs/scenarios/basic_typ.yaml` (16 ch, typ params).  
- **Sweeps:** window_ns vs BER; RIN vs BER; crosstalk vs BER; SA `I_sat` vs decision fidelity.  
- **Corners:** optimistic/typical/pessimistic packs.  
- **MoE tile scaling:** blocks → BER & aggregate throughput.  
- **Analog loop viability:** enable `amp_on`, `sat_abs_on` and sweep gains/saturation.

### 5.3 From Sim to Reality
- For each module, map **datasheet** values into YAML packs (vendorX).  
- Bench micro‑tests: measure extinction, RIN, PD dark current, TIA noise density, comparator drift; fit pack deltas.  
- Run the same scenario with *measured* packs and compare KPIs; gate promotions (PoC → Prosumer → Lab).

---

## 6) Hardware Staging & Reusability

### 6.1 Staged Builds (budget ≈ device class)
- **Stage A — <$1k PoC (Path A):**  
  Low‑power diode laser, used DLP projector, machine‑vision USB camera (global shutter), handful of glass cubes, breadboard TIAs/comparators, fiber spool (short), sorbothane mounts, blackout box.  
  *Goal:* Close the loop, demonstrate BER<5–10% on 16–64 channels; show MoE tiling and KV delay.

- **Stage B — $3–7k Prosumer:**  
  Better laser (TEC), LightCrafter DLP/HDR SLM, 10–20MP global‑shutter camera, improved TIAs, longer fiber spool, temperature control, rails/mounts.  
  *Goal:* 256–1024 channels aggregate, BER<1–2%, 100–500 tokens/s‑class for small models; reproducible demos.

- **Stage C — $25–100k Lab (add Path B elements):**  
  SOA/EDFA modules (with ASE filtering), saturable absorber cell/semiconductor SA, interferometric readout option, photorefractive crystal, modest optical table/enclosure, fast AOM+RF drive.  
  *Goal:* Validate analog ternary loop; show stage‑to‑stage propagation with threshold+gain only; WDM demo.

**Reusability:** Lasers, camera, optics table, mounts, AOM, SA, EDFA, fiber, isolation, and software carry forward across stages.

---

## 7) Performance Outlook (Order‑of‑Magnitude)

- **Stage A:** Frame‑limited (100–500 Hz); 16–256 ch; **10–200 tokens/s** small tasks; energy dominated by camera + DLP.  
- **Stage B:** 1–5 kHz frames; 256–1024 ch; **0.5–5 k tokens/s** headroom; energy/token improves 3–10× vs A.  
- **Stage C (Analog loop):** ps–ns stage latency; thousands of effective channels via WDM/tiling; **>50k tokens/s** targeted for specific kernels; energy/token set by optical power and amplifier bias.  
*Note:* These are feasibility bands; exact values depend on packs and achieved BER thresholds.

---

## 8) Risk Analysis & Mitigations

| Risk | Path | Impact | Early Signal | Mitigation |
|---|---|---|---|---|
| Coherence/time‑of‑flight spread too long | A/B | Blurred interference, high BER | BER grows with window_ns | Shorter optical path; pulse gating; interferometric reference; tighter PSF |
| Camera/DLP speed wall | A | Throughput cap | Tokens/s saturates | Move to Path B for inner loop; reduce frame‑area per expert (tiling) |
| Crosstalk across experts | A/B | Loss of independence | Correlated errors | Physical isolation, baffles, tighter tiling optics, thresholding |
| SA threshold instability | B | Drift, oscillations | BER drift vs temp | TEC; bias‑light tuning; calibration micro‑loops |
| Amplifier ASE/Noise | B | SNR collapse | BER vs gain curve | Optical filters; lower gain per stage + more stages |
| Thermal drift (index/power) | A/B | Slow BER creep | BER vs lab temp | TEC, airflow isolation, recalibration scheduler |
| Vendor parts variance | A/B | Repro issues | Pack → bench mismatch | Vendor‑specific packs; factory calib routines |
| Market/competition | – | ROI risk | Investor feedback | MoE niche kernels; IP around ternary loop & tapes |

---

## 9) Validation & Sanity‑Checks

### 9.1 Simulation Sanity
- **Unit tests per module:** deterministic seeds; closed‑form checks (e.g., shot noise scaling ~ √(I·BW)).
- **Conservation checks:** optics transmittance + stray pedestal ≤ bounds; amplifier gain maps to dB.
- **Sensitivity sweeps:** monotonic KPIs when expected (e.g., more RIN → worse BER).

### 9.2 Bench Sanity
- **Emitter:** Measure extinction (on/off power), RIN (FFT of photodiode current), drift vs °C.  
- **Optics:** Image PSF/MTF with test targets; measure stray pedestal, crosstalk by toggling tiles.  
- **PD/TIA:** Dark current vs temp; input‑referred noise density; -3 dB BW with signal generator.  
- **Comparator:** Threshold/hysteresis with ramp; temperature drift over an hour.  
- **Loop:** BER vs exposure time; BER vs optical power; repeatability day‑to‑day.

### 9.3 Model Fit
- Store measurements as **pack deltas**; run sim with measured packs; compare KPIs; update margins.  
- Flag **out‑of‑spec** behavior; propose mitigation toggle; rerun to quantify expected win.

---

## 10) Software Architecture & Extensibility

```
looking_glass/
  orchestrator.py        # wires blocks, collects KPIs
  sim/
    emitter.py           # laser/DLP/AOM model
    optics.py            # PSF/crosstalk, SA, amplifier
    sensor.py            # photodiode
    tia.py               # analog front-end
    comparator.py        # ternary decision
    clock.py             # window/jitter
    mitigations.py       # knobs (future)
  configs/
    packs/*.yaml         # parameter packs (typ/vendor/best/worst)
    scenarios/*.yaml     # end-to-end configs
examples/run_smoke.py
```

- **Parameter Packs:** YAML files map 1:1 to dataclasses; add `*_vendorX.yaml` to reflect specific devices.  
- **Scenario Runner:** (future) CLI to load a scenario, run sweeps, save CSV/plots.  
- **Drivers:** Hardware backends mirror sim API (e.g., `EmitterArray.simulate` → `EmitterArrayHW.emit`).  
- **Mitigation Flags:** Single source of truth to gate noise reductions or drifts across modules.

---

## 11) Extensions & Advanced Tricks (Opt‑in)

- **WDM/Angular multiplexing:** multiple matrices in one volume; extend `EmitterParams` for λ‑sets and `OpticsParams` for angle selectivity.  
- **Interferometric readout:** add reference arm and phase retrieval; simulate coherent addition in `optics.py`.  
- **SDR/AOM fast input:** RF‑driven ternary gating for Path B; extend `emitter.py`.  
- **Charge‑domain accumulation:** camera‑side analog pooling (Path A enhancement).  
- **Transpilation:** map logical tiles to physical sweet spots (learned routing).  
- **Dynamical decoupling:** pulse sequences to counter slow drifts (scenario toggles).  
- **Silmaril (acoustic) KV cache:** optional RF/acoustic box with SDR interface; unify via common driver.

---

## 12) Productization & Investor Lens (Snapshot)

- **Desktop co‑processor (Stage B):** Compete on $/W for specific attention kernels; MoE tiling; SDK plug‑in.  
- **Lab engine (Stage C):** Flagship demos: analog ternary loop; WDM “tape” library.  
- **Moats:** System integration know‑how, calibration/IP, ternary loop stability, parameterized simulator tightly fit to hardware (faster iteration than chip programs).

---

## 13) Roadmap & Milestones

1. **M0 (Week 0–2):** Run `run_smoke.py`; add scenario loader; CI tests; CSV logging.  
2. **M1 (Week 2–6):** Stage A bench; measure packs; close sim ↔ bench within ±3 dB noise, ±20% BER.  
3. **M2 (Week 6–12):** MoE tiling 4–8 experts; fiber delay; demo small attention block.  
4. **M3 (Quarter 2):** Stage B upgrade; 256–1024 ch; stability test (8 hours).  
5. **M4 (Quarter 3+):** Path B prototype: SA + SOA hop; WDM proof; publish whitepaper/demo.

---

## 14) How to Contribute (Modular Teams)

- **Module owners:** one owner per `sim/*` file; define test vectors and bench procedures.  
- **Packs editors:** source vendor data, keep `*_vendorX.yaml` updated and cited.  
- **HW integrators:** build micro‑rigs to measure packs; log results → `/data/measurements/*.csv`.  
- **Orchestrator:** maintains metrics, scenarios, sweep tools, plots.  
- **Critics:** review realism; propose extra gremlins; sign off on module PRs.

---

## 15) Acceptance Criteria (Stage Gates)

- **Stage A Gate:** BER ≤ 10% at 16–64 ch; stable for 30 min; sim predicts within factor 2.  
- **Stage B Gate:** BER ≤ 2% at ≥256 ch; >500 tokens/s demo; energy/token measured and within 2–3× of sim.  
- **Path B Gate:** Two optical stages chained with SA+SOA, ternary preserved end‑to‑end at ≥10 kHz equivalent rate.

---

## 16) Open Questions

- Optimal SA technology (organic film vs SESAM vs semiconductor) trade‑offs for repeatability & temp drift.  
- SOA/EDFA noise/ASE management and per‑stage gain budget.  
- Best low‑cost interferometric layout for phase readout without lab‑grade tables.  
- Practical WDM granularity for consumer‑grade sources/filters.

---

## 17) Appendix: Mapping to Code

| Block | File | Key Classes |
|---|---|---|
| Emitter | `sim/emitter.py` | `EmitterParams`, `EmitterArray` |
| Optics | `sim/optics.py` | `OpticsParams`, `Optics` |
| Photodiode | `sim/sensor.py` | `PDParams`, `Photodiode` |
| TIA | `sim/tia.py` | `TIAParams`, `TIA` |
| Comparator | `sim/comparator.py` | `ComparatorParams`, `Comparator` |
| Clock | `sim/clock.py` | `ClockParams`, `Clock` |
| System | `orchestrator.py` | `SystemParams`, `Orchestrator` |

**Scenarios & Packs:** See `configs/` for example YAMLs; create `*_vendorX.yaml` to bind to specific products, then reference in `scenarios/*.yaml`.

---

*End of DESIGN.md*
