from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base = [
        '--trials','320','--no-sweeps','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--classifier','chop', '--mask-bad-frac','0.09375',
    ]

    # Good baseline combo for reference
    optics_good = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_good = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_good = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    # Bad overlays to mix in
    optics_bad = 'configs/packs/overlays/optics_stress_ct_stray.yaml'
    comp_bad = 'configs/packs/overlays/comparator_stress_sigma.yaml'
    tia_bad = 'configs/packs/overlays/tia_stress_gainvar.yaml'

    jobs: list[dict] = []

    def add_job(tag: str, seed: int, win: str, avg: str, gate: tuple[str,str] | None,
                mask: str, opt: str, comp: str, tia: str, extras: list[str] | None = None):
        cmd = list(base) + ['--base-window-ns', win, '--avg-frames', avg, '--seed', str(seed)]
        if gate:
            cmd += ['--gate-thresh-mV', gate[0], '--gate-extra-frames', gate[1]]
        if mask:
            cmd += ['--mask-bad-frac', mask]
        if extras:
            cmd += extras
        label = f"inv2_{tag}_w{win.replace('.', 'p')}_avg{avg}_m{mask}_s{seed}"
        jobs.append({
            'cmd': cmd,
            'optics_overlay': opt,
            'comparator_overlay': comp,
            'tia_overlay': tia,
            'json_out': f"out/{label}.json",
            'label': label,
        })

    seeds = [9900, 9901]
    windows = ['18.9','19.0','19.1']  # includes ±0.1 ns jitter
    # Cases: good baseline vs one-bad overlay vs all-bad; no gating and lite gating; avg2 vs avg3; mask narrow/wide
    cases = [
        ('good', optics_good, comp_good, tia_good),
        ('optBad', optics_bad, comp_good, tia_good),
        ('compBad', optics_good, comp_bad, tia_good),
        ('tiaBad', optics_good, comp_good, tia_bad),
        ('allBad', optics_bad, comp_bad, tia_bad),
    ]

    for s in seeds:
        for win in windows:
            for tag, opt, comp, tia in cases:
                # No gating, avg2 and avg3, nominal mask
                add_job(f"{tag}_nogate", s, win, '2', None, '0.09375', opt, comp, tia)
                add_job(f"{tag}_nogate", s, win, '3', None, '0.09375', opt, comp, tia)
                # Lite gating, avg3, nominal mask
                add_job(f"{tag}_g06", s, win, '3', ('0.6','1'), '0.09375', opt, comp, tia)
                # Mask sensitivity: narrow and wide under gating
                add_job(f"{tag}_g06_m008", s, win, '3', ('0.6','1'), '0.08', opt, comp, tia)
                add_job(f"{tag}_g06_m010", s, win, '3', ('0.6','1'), '0.10', opt, comp, tia)

    # Add explicit comparator noise/sigma sweeps on good opt/TIA
    comp_noise_sweep = [
        ('n0p35_s0p20', ['--comp-input-noise-mV','0.35','--comp-vth-sigma-mV','0.20']),
        ('n0p40_s0p30', ['--comp-input-noise-mV','0.40','--comp-vth-sigma-mV','0.30']),
    ]
    for s in seeds:
        for tag, extras in comp_noise_sweep:
            add_job(f"comp_{tag}", s, '19.0', '3', ('0.6','1'), '0.09375', optics_good, comp_good, tia_good, extras)

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} invalidation stress2 jobs to {queue}")


if __name__ == '__main__':
    main()


