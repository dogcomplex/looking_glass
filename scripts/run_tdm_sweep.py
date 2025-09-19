import itertools, subprocess, json, sys
from pathlib import Path


def run(cmd):
    print('RUN', ' '.join(cmd))
    subprocess.run(cmd, check=True)


def main():
    root = Path(__file__).resolve().parents[1]
    py = root / '.venv' / 'Scripts' / 'python.exe'
    test_py = root / 'examples' / 'test.py'
    outdir = root / 'out'
    outdir.mkdir(exist_ok=True)
    optics = {
        'strong': 'configs/packs/tmp_codex_optics_medium_voa2_soa_strongsa.yaml',
        'light': 'configs/packs/tmp_codex_optics_medium_voa2_lightSA.yaml',
    }
    base = [
        str(py), str(test_py),
        '--trials', '240', '--base-window-ns', '10', '--classifier', 'chop', '--avg-frames', '2',
        '--apply-calibration', '--no-adaptive-input', '--no-cold-input', '--no-sweeps', '--light-output',
        '--emitter-pack', 'configs/packs/tmp_lowcost_emitter_boost.yaml',
        '--sensor-pack', 'configs/packs/overlays/receiver_ingaas_typ.yaml',
        '--tia-pack', 'configs/packs/overlays/tia_stage_b2_low_noise.yaml',
        '--comparator-pack', 'configs/packs/overlays/tuned_comparator.yaml',
        '--clock-pack', 'configs/packs/overlays/clock_jitter_20ps.yaml',
        '--normalize-dv', '--path-b-depth', '5', '--path-b-analog-depth', '5', '--path-b-balanced',
        '--path-b-calibrate-vth', '--path-b-calibrate-vth-scale', '0.5', '--path-b-calibrate-vth-passes', '64',
        '--path-b-stage-gains-db', '2.0,1.0,0,-0.25,-0.25', '--path-b-vth-schedule', '12,12,8,6,5',
        '--path-b-eval-active-only', '--path-b-sparse-rotate'
    ]
    combos = []
    for ch in (16, 32):
        for tier, opt in optics.items():
            for k in (4, 8):
                combos.append((ch, tier, opt, k, 'emitter', 0.0))
                combos.append((ch, tier, opt, k, 'eo_switch', 0.5))
    rows = []
    for ch, tier, opt, k, mode, t_sw in combos:
        tag = f'tdm_sweep_{ch}ch_{tier}_k{k}_{mode}_tsw{t_sw}'.replace('.', 'p')
        out = outdir / f'{tag}.json'
        cmd = base + [
            '--channels', str(ch), '--optics-pack', opt, '--path-b-sparse-active-k', str(k),
            '--tdm-switch-mode', str(mode), '--tdm-switch-t-ns', str(t_sw),
            '--json', str(out), '--quiet'
        ]
        run(cmd)
        rows.append(str(out))
    # Summarize
    summ = outdir / 'tdm_sweep_summary.csv'
    run([str(py), str(root / 'scripts' / 'summarize_tdm.py'), *rows, str(summ)])
    print('Sweep summary at', summ)


if __name__ == '__main__':
    main()
