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
        '--classifier','chop',
    ]

    # Curated overlays
    optics = {
        'A': 'configs/packs/overlays/optics_stage_a_hygiene.yaml',
        'E': 'configs/packs/overlays/optics_stage_e_power_mod.yaml',
        'E2': 'configs/packs/overlays/optics_stage_e2_power_mod.yaml',
        'F': 'configs/packs/overlays/optics_stage_f_amp.yaml',
        'G': 'configs/packs/overlays/optics_stage_g_saturable.yaml',
    }
    comps = {
        'T': 'configs/packs/overlays/tuned_comparator.yaml',
        'C2': 'configs/packs/overlays/comparator_stage_c2_trims.yaml',
        'C3': 'configs/packs/overlays/comparator_stage_c3_precision.yaml',
    }
    tias = {
        'T': 'configs/packs/overlays/tuned_tia.yaml',
        'B2': 'configs/packs/overlays/tia_stage_b2_low_noise.yaml',
        'B3': 'configs/packs/overlays/tia_stage_b3_precision.yaml',
    }

    # Small grid: windows, masks, avg, gating
    windows = ['18.9','19.0','19.1']
    masks = ['0.09125','0.09375']
    avgs = ['2','3']
    gates = [('0.6','1'),('0.8','1')]

    # Combos to try (kept small)
    combos = [
        ('A','T','T'),
        ('E','C2','B2'),
        ('E2','C2','B2'),
        ('F','C3','B3'),
        ('G','C3','B3'),
    ]

    jobs: list[dict] = []
    seed = 8600
    for o,c,t in combos:
        for w in windows:
            for m in masks:
                for a in avgs:
                    for g in gates:
                        cmd = list(base) + ['--base-window-ns', w, '--avg-frames', a, '--mask-bad-frac', m,
                                             '--seed', str(seed), '--gate-thresh-mV', g[0], '--gate-extra-frames', g[1]]
                        label = f"swh_{o}{c}{t}_w{w.replace('.', 'p')}_avg{a}_m{m}_s{seed}_g{g[0].replace('.', 'p')}e{g[1]}"
                        jobs.append({
                            'cmd': cmd,
                            'optics_overlay': optics[o],
                            'comparator_overlay': comps[c],
                            'tia_overlay': tias[t],
                            'json_out': f"out/{label}.json",
                            'label': label,
                        })
                        seed += 1

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} hardware compact sweep jobs to {queue}")


if __name__ == '__main__':
    main()


