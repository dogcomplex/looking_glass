from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--normalize-dv',
        '--no-adaptive-input','--no-cold-input','--no-path-b',
        '--path-b-depth','0','--no-path-b-analog',
    ]

    def mk_job(name: str, extra: list[str]) -> dict:
        cmd = list(base) + extra
        return {
            'cmd': cmd,
            'optics_overlay': 'configs/packs/overlays/optics_low_ct.yaml',
            'comparator_overlay': 'configs/packs/overlays/tuned_comparator.yaml',
            'tia_overlay': 'configs/packs/overlays/tuned_tia.yaml',
            'json_out': f"out/{name}.json",
            'label': name,
        }

    windows = ['18.9','19.0','19.1']
    masks = ['0.085','0.09','0.09375','0.10']

    jobs: list[dict] = []
    seed = 9100

    # Force calibrated corrections into primary via existing path flags in test.py
    # Sweep chop with avg3 base and small gating variants
    for w in windows:
        for m in masks:
            name = f"s3_calnorm_chop_w{w.replace('.', 'p')}_avg3_m{m}_s{seed}"
            extra = ['--base-window-ns', w, '--classifier', 'chop', '--avg-frames','3', '--mask-bad-frac', m, '--seed', str(seed)]
            jobs.append(mk_job(name, extra))
            # lite gating variants
            for gt, ge in [('0.6','1'), ('1.0','2')]:
                gname = f"{name}_gate{gt.replace('.', 'p')}e{ge}"
                gextra = extra + ['--gate-thresh-mV', gt, '--gate-extra-frames', ge]
                jobs.append(mk_job(gname, gextra))

    # Lockin controls avg2
    for w in windows:
        for m in masks:
            name = f"s3_calnorm_lockin_w{w.replace('.', 'p')}_avg2_m{m}_s{seed}"
            extra = ['--base-window-ns', w, '--classifier', 'lockin', '--avg-frames','2', '--mask-bad-frac', m, '--seed', str(seed)]
            jobs.append(mk_job(name, extra))

    with queue.open('a', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} sweep3 jobs to {queue}")


if __name__ == '__main__':
    main()




