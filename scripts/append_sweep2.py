from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base_common = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--base-window-ns','19.0',  # default; will override per job
    ]

    def mk_job(seed: int, cls: str, win: str, avg: str, mask: str, extra: list[str] | None = None) -> dict:
        cmd = list(base_common)
        cmd += ['--base-window-ns', win, '--classifier', cls, '--avg-frames', avg, '--mask-bad-frac', mask, '--seed', str(seed)]
        if extra:
            cmd += extra
        label = f"s2_{cls}_w{win.replace('.', 'p')}_avg{avg}_m{mask}_s{seed}"
        return {
            'cmd': cmd,
            'optics_overlay': 'configs/packs/overlays/optics_low_ct.yaml',
            'comparator_overlay': 'configs/packs/overlays/tuned_comparator.yaml',
            'tia_overlay': 'configs/packs/overlays/tuned_tia.yaml',
            'json_out': f"out/{label}.json",
            'label': label,
        }

    windows = ['18.8','19.0','19.2']
    avgs = ['2','3','4']
    # finer mask sweep around best
    masks = [
        '0.07','0.075','0.08','0.085','0.09','0.09375','0.10','0.105','0.11'
    ]

    jobs: list[dict] = []
    seeds = [8000, 8001]

    # Primary: chop generous sweep
    for seed in seeds:
        for win in windows:
            for avg in avgs:
                for mask in masks:
                    jobs.append(mk_job(seed, 'chop', win, avg, mask))
    # Lite gating only for avg3
    for seed in seeds:
        for win in windows:
            for mask in masks:
                jobs.append(mk_job(seed, 'chop', win, '3', mask, extra=['--gate-thresh-mV','0.6','--gate-extra-frames','1']))
                jobs.append(mk_job(seed, 'chop', win, '3', mask, extra=['--gate-thresh-mV','1.0','--gate-extra-frames','2']))

    # Control slice for lockin (narrower, avg2/3 only)
    for seed in seeds:
        for win in windows:
            for avg in ['2','3']:
                for mask in masks:
                    jobs.append(mk_job(seed, 'lockin', win, avg, mask))

    with queue.open('a', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} sweep2 jobs to {queue}")


if __name__ == '__main__':
    main()




