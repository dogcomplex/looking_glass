from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics_e2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    optics_grid512 = 'configs/packs/overlays/optics_accept_grid512.yaml'

    # Combined acceptance: Vth import + normalize + strong hysteresis
    for ch in ['16','32']:
        export_label = f"accept_combo_export_vth_ch{ch}_w19p0_avg3_m0.09375_s9971"
        jobs.append({
            'label': export_label,
            'cmd': ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3','--mask-bad-frac','0.09375','--seed','9971'],
            'optics_overlay': optics_e2,'comparator_overlay': comp,'tia_overlay': tia,
            'export_vth': f"out/{export_label}_vth.json",'json_out': f"out/{export_label}.json"
        })
        import_label = f"accept_combo_import_norm_h0p8_ch{ch}_w19p0_avg3_m0.09375_s9972_g0p6e1"
        jobs.append({
            'label': import_label,
            'cmd': ['--trials','1400','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3','--mask-bad-frac','0.09375','--seed','9972','--gate-thresh-mV','0.6','--gate-extra-frames','1','--normalize-dv','--comp-hysteresis-mV','0.8'],
            'optics_overlay': optics_e2,'comparator_overlay': comp,'tia_overlay': tia,
            'import_vth': f"out/{export_label}_vth.json",'json_out': f"out/{import_label}.json"
        })

    # Grid512 acceptance variant at 16 ch
    for w in ['18.95','19.0','19.05']:
        label = f"accept_grid512_ch16_w{w.replace('.','p')}_avg3_m0.09375_s9973_g0p6e1_norm_h0p8"
        cmd = ['--trials','1400','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels','16','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac','0.09375','--seed','9973','--gate-thresh-mV','0.6','--gate-extra-frames','1','--normalize-dv','--comp-hysteresis-mV','0.8']
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_grid512,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Path B depth=8, low per-stage gain with soft SA
    optics_amp4 = 'configs/packs/overlays/optics_stage_f_amp_g4.yaml'
    optics_sa_soft = 'configs/packs/overlays/optics_stage_g_saturable_soft.yaml'
    for opt, tag in ((optics_amp4,'amp4'), (optics_sa_soft,'sa_soft')):
        cmd = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','16','--base-window-ns','19.0','--avg-frames','3','--mask-bad-frac','0.09375','--seed','9981','--path-b-analog-depth','8']
        label = f"pathb_d8_{tag}_ch16_w19p0_avg3_m0.09375_s9981"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': opt,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} acceptance combo + PathB d8 jobs to {queue}")


if __name__ == '__main__':
    main()


