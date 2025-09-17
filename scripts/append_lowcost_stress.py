from __future__ import annotations
import json
from pathlib import Path

def append_jobs(jobs: list[dict]) -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)
    with queue.open('a', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} low-cost stress jobs to {queue}")

def main() -> None:
    jobs: list[dict] = []

    # High crosstalk + drift stress with calibration enabled.
    stress_cmd = [
        '--trials','400','--light-output','--channels','8','--base-window-ns','6.0','--seed','7123',
        '--classifier','chop','--chop','--avg-frames','2','--gate-thresh-mV','0.6','--gate-extra-frames','1',
        '--apply-calibration','--mask-bad-frac','0.0625','--no-adaptive-input','--no-cold-input','--no-path-b',
        '--decoder-linear','--decoder-samples','200','--use-decoder-for-path-a','--normalize-dv'
    ]
    jobs.append({
        'label': 'tile8_ctstress_cal',
        'cmd': stress_cmd,
        'emitter_pack': 'configs/packs/tmp_led_array.yaml',
        'optics_pack': 'configs/packs/tmp_codex_optics_highct.yaml',
        'sensor_pack': 'configs/packs/tmp_budget_sensor.yaml',
        'tia_pack': 'configs/packs/tmp_budget_tia.yaml',
        'comparator_pack': 'configs/packs/tmp_budget_comparator.yaml',
        'clock_pack': 'configs/packs/tmp_budget_clock_heavy.yaml',
        'thermal_pack': 'configs/packs/tmp_thermal_drift_heavy.yaml',
        'json_out': 'out/tile8_ctstress_cal.json'
    })

    # Same hardware, mitigations removed to map failure boundary.
    stress_nomitig_cmd = [
        '--trials','400','--light-output','--channels','8','--base-window-ns','6.0','--seed','7124',
        '--classifier','chop','--chop','--avg-frames','1','--gate-thresh-mV','0.0','--gate-extra-frames','0',
        '--apply-calibration','--mask-bad-frac','0.0','--no-adaptive-input','--no-cold-input','--no-path-b',
        '--decoder-linear','--decoder-samples','200','--use-decoder-for-path-a'
    ]
    jobs.append({
        'label': 'tile8_ctstress_nomitig',
        'cmd': stress_nomitig_cmd,
        'emitter_pack': 'configs/packs/tmp_led_array_stress.yaml',
        'optics_pack': 'configs/packs/tmp_codex_optics_highct.yaml',
        'sensor_pack': 'configs/packs/tmp_budget_sensor.yaml',
        'tia_pack': 'configs/packs/tmp_budget_tia.yaml',
        'comparator_pack': 'configs/packs/tmp_budget_comparator.yaml',
        'clock_pack': 'configs/packs/tmp_budget_clock_heavy.yaml',
        'thermal_pack': 'configs/packs/tmp_thermal_drift_heavy.yaml',
        'json_out': 'out/tile8_ctstress_nomitig.json'
    })

    append_jobs(jobs)

if __name__ == '__main__':
    main()
