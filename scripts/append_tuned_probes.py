from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base = [
        '--trials','320',
        '--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--normalize-dv',
        '--calib-mask-trials','240','--calib-samples','400',
        '--base-window-ns','19.0',
        '--classifier','avg','--avg-frames','11',
    ]

    def J(seed: int, mask: float, tia_overlay: str, win: str = '19.0') -> dict:
        cmd = list(base)
        cmd[cmd.index('--base-window-ns')+1] = win
        cmd += ['--seed', str(seed), '--mask-bad-frac', str(mask)]
        return {
            'cmd': cmd,
            'optics_overlay': 'configs/packs/overlays/optics_low_ct.yaml',
            'comparator_overlay': 'configs/packs/overlays/tuned_comparator.yaml',
            'tia_overlay': tia_overlay,
            'json_out': f"out/tuned_w{win.replace('.', 'p')}_avg11_m{mask}_s{seed}.json",
            'label': f"tuned_w{win}_avg11_m{mask}_s{seed}",
        }

    jobs = [
        J(5091, 0.09375, 'configs/packs/overlays/tuned_tia.yaml', '19.0'),
        J(5092, 0.0625,  'configs/packs/overlays/tuned_tia.yaml', '19.0'),
        J(5093, 0.09375, 'configs/packs/overlays/tia_12k_65.yaml', '19.0'),
        J(5094, 0.0625,  'configs/packs/overlays/tia_12k_65.yaml', '19.0'),
        J(5095, 0.09375, 'configs/packs/overlays/tuned_tia.yaml',  '18.0'),
        J(5096, 0.0625,  'configs/packs/overlays/tuned_tia.yaml',  '18.0'),
    ]

    with queue.open('a', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, separators=(',', ':')) + '\n')
    print(f'appended {len(jobs)} tuned jobs to {queue}')


if __name__ == '__main__':
    main()



