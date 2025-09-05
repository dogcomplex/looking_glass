from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	fiber_stress = 'configs/packs/overlays/fiber_cband_loop_stress.yaml'
	comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
	tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
	soa_budget = 'configs/packs/overlays/soa_chain_budget.yaml'
	edfa_budget = 'configs/packs/overlays/edfa_chain_budget.yaml'

	recover_flags = [
		'--classifier','chop',
		'--normalize-dv','--normalize-eps-v','1e-6',
		'--avg-frames','3','--use-avg-frames-for-path-a',
		'--gate-thresh-mV','0.6',
		'--mask-bad-frac','0.05',
		'--apply-calibration'
	]

	# Sweep 1: BER vs window for 8-ch EDFA tile under stress
	for win in [4.0, 5.0, 6.0, 8.0, 10.0]:
		label = f'cband_recover_win_sweep_edfa8_w{str(win).replace(".","p")}ns_s120{int(win*10):02d}'
		cmd = ['--trials','600','--no-sweeps','--light-output','--channels','8','--base-window-ns',str(win),'--seed',str(12000+int(win*10)),'--path-b-analog-depth','10'] + recover_flags
		jobs.append({'label': label,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': fiber_stress,'optics_pack': edfa_budget,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

	# Sweep 2: BER vs depth for 1-ch SOA under stress at 6 ns
	for depth in [8, 12, 16, 24, 32]:
		label = f'cband_recover_depth_sweep_soa1_d{depth}_w6p0ns_s121{depth:02d}'
		cmd = ['--trials','600','--no-sweeps','--light-output','--channels','1','--base-window-ns','6.0','--seed',str(12100+depth),'--path-b-analog-depth',str(depth)] + recover_flags
		jobs.append({'label': label,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': fiber_stress,'optics_pack': soa_budget,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} c-band recovery sweep tests to {queue}")


if __name__ == '__main__':
	main()
