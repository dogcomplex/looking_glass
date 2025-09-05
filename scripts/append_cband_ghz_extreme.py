from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	fiber = 'configs/packs/overlays/fiber_cband_loop_typ.yaml'
	comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
	tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
	edfa_budget = 'configs/packs/overlays/edfa_chain_budget.yaml'
	soa_budget = 'configs/packs/overlays/soa_chain_budget.yaml'

	windows = ['6.0','8.0','10.0']
	depths = ['10','12','16','24','32']
	masks = ['0.05']

	for w in windows:
		for d in depths:
			# Single-λ SOA budget extreme
			lab = f"cband_ext_soa_d{d}_w{w.replace('.','p')}_s11501"
			cmd = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','1','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac', masks[0],'--seed','11501','--path-b-analog-depth', d]
			job = {'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': fiber,'optics_pack': soa_budget,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab}.json"}
			# Inject system and comparator jitter via args understood by runner
			job['lane_skew_ps_rms'] = 12.0
			job['pmd_ps_rms'] = 12.0
			job['comp_prop_jitter_ps_rms'] = 10.0
			jobs.append(job)
			# 8-λ EDFA budget extreme
			lab2 = f"cband_ext_edfa_tile_d{d}_w{w.replace('.','p')}_s11502"
			cmd2 = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','8','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac', masks[0],'--seed','11502','--path-b-analog-depth', d]
			job2 = {'label': lab2,'cmd': cmd2,'emitter_pack': emitter,'optics_overlay': fiber,'optics_pack': edfa_budget,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab2}.json"}
			job2['lane_skew_ps_rms'] = 12.0
			job2['pmd_ps_rms'] = 12.0
			job2['comp_prop_jitter_ps_rms'] = 10.0
			jobs.append(job2)

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} c-band extreme GHz jobs to {queue}")


if __name__ == '__main__':
	main()
