from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--base-window-ns','19.0', '--mask-bad-frac','0.09375', '--seed','9500',
    ]

    optics_E2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_C2 = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_B2 = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    jobs: list[dict] = []

    # 1) Replicate/majority vote (simulate MoE style redundancy across optical tiles)
    # Use existing replicate classifiers if present; otherwise, emulate via avg/gating combos.
    for cls in ['replicate', 'replicate2', 'vote5']:
        cmd = list(base) + ['--classifier', cls, '--avg-frames','2']
        label = f"moe_{cls}_avg2_m0.09375_s9500"
        jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})
        cmd = list(base) + ['--classifier', cls, '--avg-frames','2','--gate-thresh-mV','0.6','--gate-extra-frames','1']
        label = f"moe_{cls}_avg2_m0.09375_s9500_g0p6e1"
        jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})

    # 2) Decoder + ECC (linear decoder with small L2 + single-parity block ECC)
    cmd = list(base) + ['--classifier','chop','--avg-frames','2','--gate-thresh-mV','0.6','--gate-extra-frames','1',
                        '--decoder-linear','--decoder-l2','1e-3','--decoder-samples','240',
                        '--use-ecc','--ecc-spc-block','4']
    label = 'moe_decoder_ecc_chop_avg2_g0p6e1'
    jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})

    # 3) Soft/vote fusion with lite gating (if fuse-decoder supported)
    cmd = list(base) + ['--classifier','chop','--avg-frames','2','--gate-thresh-mV','0.6','--gate-extra-frames','1',
                        '--decoder-linear','--decoder-l2','1e-3','--decoder-samples','240',
                        '--fuse-decoder','--fuse-alpha','0.7']
    label = 'moe_decoder_fuse_chop_avg2_g0p6e1'
    jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} MoE compensation jobs to {queue}")


if __name__ == '__main__':
    main()


