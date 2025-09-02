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
        '--base-window-ns','19.0','--classifier','chop','--avg-frames','3',
        '--mask-bad-frac','0.09375',
    ]

    def J(seed: int, extra: list[str]) -> dict:
        return {
            'cmd': base + ['--seed', str(seed)] + extra,
            'optics_overlay': 'configs/packs/overlays/optics_low_ct.yaml',
            'comparator_overlay': 'configs/packs/overlays/tuned_comparator.yaml',
            'tia_overlay': 'configs/packs/overlays/tuned_tia.yaml',
            'json_out': f'out/focus19_chop_avg3_m09375_s{seed}.json',
            'label': f'focus19_chop_avg3_m09375_s{seed}',
        }

    jobs = [
        J(6001, []),
        J(6002, ['--force-cal-in-primary']),
        J(6003, ['--force-cal-in-primary','--gate-thresh-mV','0.6','--gate-extra-frames','1']),
        J(6004, ['--force-cal-in-primary','--gate-thresh-mV','1.0','--gate-extra-frames','2']),
        J(6005, ['--force-cal-in-primary','--optimize-vth','--opt-vth-iters','3','--opt-vth-step-mV','0.1','--opt-vth-use-mask']),
        J(6006, ['--force-cal-in-primary','--optimize-linear','--opt-lin-iters','4','--opt-lin-step-mV','0.1','--opt-lin-use-mask']),
        J(6007, ['--force-cal-in-primary','--optimize-vth','--opt-vth-iters','3','--opt-vth-step-mV','0.1','--opt-vth-use-mask','--optimize-linear','--opt-lin-iters','4','--opt-lin-step-mV','0.1','--opt-lin-use-mask']),
        J(6008, ['--force-cal-in-primary','--gate-thresh-mV','0.6','--gate-extra-frames','1','--optimize-linear','--opt-lin-iters','3','--opt-lin-step-mV','0.08','--opt-lin-use-mask']),
    ]

    with queue.open('a', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, separators=(',', ':')) + '\n')
    print(f'appended {len(jobs)} focus19 jobs to {queue}')

if __name__ == '__main__':
    main()

