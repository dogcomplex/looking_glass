from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics_iso_stronger = 'configs/packs/overlays/optics_projector_iso_stronger.yaml'

    # Refine multi-channel: stronger isolation, avg3, normalize, lite gate 0.6, mask 5%, windows 20–24
    chans = ['32','128','256','512']
    windows = ['20.0','21.0','22.0','23.0','24.0']
    for ch in chans:
        for w in windows:
            cmd = ['--trials','800','--no-sweeps','--no-drift','--light-output','--apply-calibration',
                   '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                   '--classifier','chop','--channels', ch,
                   '--base-window-ns', w,'--avg-frames','3','--normalize-dv',
                   '--gate-thresh-mV','0.6','--gate-extra-frames','1','--mask-bad-frac','0.05',
                   '--seed','14301']
            label = f"refine_iso_stronger_ch{ch}_w{w.replace('.','p')}_avg3_norm_g0p6e1_m0p05"
            jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_iso_stronger,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} multi-channel refine jobs to {queue}")


if __name__ == '__main__':
    main()


