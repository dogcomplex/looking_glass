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

    def J(tag: str, seed: int, avg: str, mask: str, gate: tuple[str,str], extras: list[str] | None = None) -> dict:
        cmd = list(base) + ['--avg-frames', avg, '--mask-bad-frac', mask, '--seed', str(seed), '--gate-thresh-mV', gate[0], '--gate-extra-frames', gate[1]]
        if extras:
            cmd += extras
        label = f"diag_{tag}_w19p0_avg{avg}_m{mask}_s{seed}_g{gate[0].replace('.', 'p')}e{gate[1]}"
        return {
            'cmd': cmd,
            'optics_overlay': optics_E2,
            'comparator_overlay': comp_C2,
            'tia_overlay': tia_B2,
            'json_out': f"out/{label}.json",
            'label': label,
        }

    jobs = [
        # Wider masks (diagnostic only)
        J('C2B2E2', 8480, '3', '0.10', ('1.2','2')),
        J('C2B2E2', 8481, '3', '0.12', ('1.2','2')),
        # dvspan mask compare
        J('C2B2E2_dvspan', 8482, '3', '0.10', ('1.0','2'), ['--mask-mode','dvspan']),
        J('C2B2E2_dvspan', 8483, '3', '0.12', ('1.0','2'), ['--mask-mode','dvspan']),
        # avg4 variant at 0.10
        J('C2B2E2', 8484, '4', '0.10', ('0.8','1')),
        # enable use_avg_frames_for_path_a to ensure primary uses averaging path
        J('C2B2E2_useavg', 8485, '3', '0.10', ('0.8','1'), ['--use-avg-frames-for-path-a']),
    ]

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} acceptance diag jobs to {queue}")


if __name__ == '__main__':
    main()


