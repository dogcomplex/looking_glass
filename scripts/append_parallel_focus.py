from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    classifiers = ['chop', 'lockin']
    windows = ['18.8', '19.0', '19.2']
    avg_frames = ['2', '3', '4']
    masks = ['0.085', '0.09375', '0.11']

    base_common = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
    ]

    def mk_job(seed: int, cls: str, win: str, avg: str, mask: str, extra: list[str] | None = None) -> dict:
        cmd = list(base_common)
        cmd += ['--base-window-ns', win, '--classifier', cls, '--avg-frames', avg, '--mask-bad-frac', mask, '--seed', str(seed)]
        if extra:
            cmd += extra
        label = f"par_{cls}_w{win.replace('.', 'p')}_avg{avg}_m{mask}_s{seed}"
        return {
            'cmd': cmd,
            'optics_overlay': 'configs/packs/overlays/optics_low_ct.yaml',
            'comparator_overlay': 'configs/packs/overlays/tuned_comparator.yaml',
            'tia_overlay': 'configs/packs/overlays/tuned_tia.yaml',
            'json_out': f"out/{label}.json",
            'label': label,
        }

    jobs: list[dict] = []
    seed_base = 7000
    idx = 0
    # Base grid (no gating, no force-cal)
    for cls in classifiers:
        for win in windows:
            for avg in avg_frames:
                for mask in masks:
                    jobs.append(mk_job(seed_base + idx, cls, win, avg, mask))
                    idx += 1
    # Lite gating only for avg3
    for cls in classifiers:
        for win in windows:
            for mask in masks:
                jobs.append(mk_job(seed_base + idx, cls, win, '3', mask, extra=['--gate-thresh-mV','0.6','--gate-extra-frames','1']))
                idx += 1

    with queue.open('a', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} parallel focus jobs to {queue}")


if __name__ == '__main__':
    main()



