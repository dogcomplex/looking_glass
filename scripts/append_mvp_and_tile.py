from __future__ import annotations
import json
from pathlib import Path

def append_jobs(jobs: list[dict]) -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)
    with queue.open('a', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} MVP/tile jobs to {queue}")

def main() -> None:
    jobs: list[dict] = []

    # Single-channel MVP (one-pass) using low-cost LED + budget front-end.
    mvp_cmd = [
        '--trials','400','--light-output','--channels','1','--base-window-ns','6.0','--seed','7001',
        '--classifier','chop','--chop','--avg-frames','2','--gate-thresh-mV','0.6','--gate-extra-frames','1',
        '--apply-calibration','--mask-bad-frac','0.0','--no-adaptive-input','--no-cold-input','--no-path-b',
        '--decoder-linear','--decoder-samples','200','--use-decoder-for-path-a','--normalize-dv'
    ]
    jobs.append({
        'label': 'mvp_sc1_led_w6p0',
        'cmd': mvp_cmd,
        'emitter_pack': 'configs/packs/tmp_led_array.yaml',
        'optics_pack': 'configs/packs/tmp_codex_optics_medium.yaml',
        'sensor_pack': 'configs/packs/tmp_budget_sensor.yaml',
        'tia_pack': 'configs/packs/tmp_budget_tia.yaml',
        'comparator_pack': 'configs/packs/tmp_budget_comparator.yaml',
        'clock_pack': 'configs/packs/tmp_budget_clock.yaml',
        'thermal_pack': 'configs/packs/thermal_typ.yaml',
        'json_out': 'out/mvp_sc1_led_w6p0.json'
    })

    # 8-channel split tile baseline (low-cost stack, low crosstalk optics).
    tile_cmd = [
        '--trials','400','--light-output','--channels','8','--base-window-ns','6.0','--seed','6023',
        '--classifier','chop','--chop','--avg-frames','2','--gate-thresh-mV','0.6','--gate-extra-frames','1',
        '--apply-calibration','--mask-bad-frac','0.0625','--no-adaptive-input','--no-cold-input','--no-path-b',
        '--decoder-linear','--decoder-samples','200','--use-decoder-for-path-a','--normalize-dv'
    ]
    jobs.append({
        'label': 'tile8_lowcost_w6p0',
        'cmd': tile_cmd,
        'emitter_pack': 'configs/packs/tmp_led_array.yaml',
        'optics_pack': 'configs/packs/tmp_codex_optics_lowct.yaml',
        'sensor_pack': 'configs/packs/tmp_budget_sensor.yaml',
        'tia_pack': 'configs/packs/tmp_budget_tia.yaml',
        'comparator_pack': 'configs/packs/tmp_budget_comparator.yaml',
        'clock_pack': 'configs/packs/tmp_budget_clock.yaml',
        'thermal_pack': 'configs/packs/thermal_typ.yaml',
        'json_out': 'out/tile8_lowcost_w6p0.json'
    })

    # 16-channel dual-wavelength tile (WDM + mode mixing proxy).
    wdm_cmd = [
        '--trials','400','--light-output','--channels','16','--base-window-ns','6.0','--seed','7201',
        '--classifier','chop','--chop','--avg-frames','2','--gate-thresh-mV','0.6','--gate-extra-frames','1',
        '--apply-calibration','--mask-bad-frac','0.0625','--no-adaptive-input','--decoder-linear','--decoder-samples','200',
        '--use-decoder-for-path-a','--normalize-dv'
    ]
    jobs.append({
        'label': 'tile16_wdm_dual',
        'cmd': wdm_cmd,
        'emitter_pack': 'configs/packs/overlays/emitter_dual_wdm.yaml',
        'optics_pack': 'configs/packs/overlays/optics_mode_mix_dual.yaml',
        'sensor_pack': 'configs/packs/tmp_budget_sensor.yaml',
        'tia_pack': 'configs/packs/tmp_budget_tia.yaml',
        'comparator_pack': 'configs/packs/tmp_budget_comparator.yaml',
        'clock_pack': 'configs/packs/tmp_budget_clock.yaml',
        'thermal_pack': 'configs/packs/thermal_typ.yaml',
        'json_out': 'out/tile16_wdm_dual.json'
    })

    append_jobs(jobs)

if __name__ == '__main__':
    main()
