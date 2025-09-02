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
        '--classifier','chop','--base-window-ns','19.0',
    ]

    optics_E2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_C2 = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_B2 = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    def J(tag: str, seed: int, avg: str, mask: str, gate: tuple[str,str]) -> dict:
        cmd = list(base) + ['--avg-frames', avg, '--mask-bad-frac', mask, '--seed', str(seed), '--gate-thresh-mV', gate[0], '--gate-extra-frames', gate[1]]
        label = f"acc_{tag}_w19p0_avg{avg}_m{mask}_s{seed}_g{gate[0].replace('.', 'p')}e{gate[1]}"
        return {
            'cmd': cmd,
            'optics_overlay': optics_E2,
            'comparator_overlay': comp_C2,
            'tia_overlay': tia_B2,
            'json_out': f"out/{label}.json",
            'label': label,
        }

    jobs = [
        J('C2B2E2', 8460, '3', '0.09375', ('0.6','1')),
        J('C2B2E2', 8461, '3', '0.09375', ('0.8','1')),
        J('C2B2E2', 8462, '3', '0.09375', ('1.2','2')),
        J('C2B2E2', 8463, '2', '0.09375', ('1.0','1')),
        # jitter check
        {
            'cmd': base + ['--avg-frames','3','--mask-bad-frac','0.09375','--seed','8464','--gate-thresh-mV','0.6','--gate-extra-frames','1','--base-window-ns','18.95'],
            'optics_overlay': optics_E2,
            'comparator_overlay': comp_C2,
            'tia_overlay': tia_B2,
            'json_out': 'out/acc_C2B2E2_w18p95_avg3_m0.09375_s8464_g0p6e1.json',
            'label': 'acc_C2B2E2_w18p95_avg3_m0.09375_s8464_g0p6e1',
        },
        {
            'cmd': base + ['--avg-frames','3','--mask-bad-frac','0.09375','--seed','8465','--gate-thresh-mV','0.6','--gate-extra-frames','1','--base-window-ns','19.05'],
            'optics_overlay': optics_E2,
            'comparator_overlay': comp_C2,
            'tia_overlay': tia_B2,
            'json_out': 'out/acc_C2B2E2_w19p05_avg3_m0.09375_s8465_g0p6e1.json',
            'label': 'acc_C2B2E2_w19p05_avg3_m0.09375_s8465_g0p6e1',
        },
    ]

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} acceptance jobs to {queue}")


if __name__ == '__main__':
    main()
