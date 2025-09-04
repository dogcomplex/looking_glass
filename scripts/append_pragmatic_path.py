from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    # Common good overlays (Path A PD path unless camera overlay provided)
    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics_good = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    optics_iso = 'configs/packs/overlays/optics_projector_isolated.yaml'  # uses tile borders/isolation
    optics_amp = 'configs/packs/overlays/optics_stage_f_amp.yaml'
    optics_sa = 'configs/packs/overlays/optics_stage_g_saturable.yaml'
    optics_both = 'configs/packs/overlays/optics_stage_fg_amp_sat.yaml'

    # Phase 1: Single-PD MVP (Path A, electronic ternary) — PD path (no camera overlay)
    phase1 = [
        ('p1_pd_w10',  ['--channels','1','--base-window-ns','10.0','--avg-frames','1']),
        ('p1_pd_w5',   ['--channels','1','--base-window-ns','5.0','--avg-frames','1']),
        ('p1_pd_w2',   ['--channels','1','--base-window-ns','2.0','--avg-frames','1']),
    ]
    for tag, args in phase1:
        cmd = ['--trials','320','--no-sweeps','--no-drift','--light-output','--apply-calibration',
               '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
               '--classifier','avg','--seed','13101'] + args
        label = f"prag_{tag}"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_good,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Phase 2: Fast gating proxy (short window) — still PD read
    phase2 = [
        ('p2_fast_w1',  ['--channels','1','--base-window-ns','1.0','--avg-frames','1']),
        ('p2_fast_w0p5',['--channels','1','--base-window-ns','0.5','--avg-frames','1']),
    ]
    for tag, args in phase2:
        cmd = ['--trials','320','--no-sweeps','--no-drift','--light-output','--apply-calibration',
               '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
               '--classifier','avg','--seed','13102'] + args
        label = f"prag_{tag}"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_good,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Phase 3: Path B single hop (amp and/or SA) — PD read
    phase3 = [
        ('p3_pathb_amp',      optics_amp),
        ('p3_pathb_sa',       optics_sa),
        ('p3_pathb_amp_sa',   optics_both),
    ]
    for tag, opt in phase3:
        cmd = ['--trials','320','--no-sweeps','--no-drift','--light-output','--apply-calibration',
               '--no-adaptive-input','--base-window-ns','5.0','--classifier','avg','--avg-frames','1',
               '--seed','13103', '--path-b-analog-depth','1']
        label = f"prag_{tag}_ch1"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': opt,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Phase 4: PD banks (32/128/256/512) with isolation borders, normalize, lite gating
    phase4_ch = ['32','128','256','512']
    for ch in phase4_ch:
        cmd = ['--trials','320','--no-sweeps','--no-drift','--light-output','--apply-calibration',
               '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
               '--classifier','chop','--channels', ch,
               '--base-window-ns','19.0','--avg-frames','2','--normalize-dv',
               '--gate-thresh-mV','0.6','--gate-extra-frames','1','--mask-bad-frac','0.07',
               '--seed','13104']
        label = f"prag_p4_iso_ch{ch}_avg2_norm_g0p6e1_m0p07"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_iso,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Phase 5: Shared SA+amp with PD banks (time-multiplex depth 2)
    phase5_ch = ['128','256']
    for ch in phase5_ch:
        cmd = ['--trials','320','--no-sweeps','--no-drift','--light-output','--apply-calibration',
               '--no-adaptive-input','--classifier','chop','--channels', ch,
               '--base-window-ns','19.0','--avg-frames','2','--normalize-dv',
               '--gate-thresh-mV','0.6','--gate-extra-frames','1','--mask-bad-frac','0.05',
               '--seed','13105', '--path-b-analog-depth','2']
        label = f"prag_p5_pathb_amp_sa_ch{ch}_avg2_norm_g0p6e1_m0p05_d2"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_both,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} pragmatic build-path jobs to {queue}")


if __name__ == '__main__':
    main()


