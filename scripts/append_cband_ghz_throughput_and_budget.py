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
	recv_low = 'configs/packs/overlays/receiver_ingaas_lowbw.yaml'
	soa_budget = 'configs/packs/overlays/soa_chain_budget.yaml'
	edfa_budget = 'configs/packs/overlays/edfa_chain_budget.yaml'

	# GHz timing windows and jitter proxy (we piggyback via shorter windows and low-BW receiver)
	windows = ['6.0','8.0','10.0']
	depths = ['2','4','6','8']
	masks = ['0.05','0.09375']

	for w in windows:
		for d in depths:
			for m in masks:
				# Budget SOA path, single-\u03bb
				lab = f"cband_ghz_soa_budget_d{d}_w{w.replace('.','p')}_avg3_m{m}_s11401"
				cmd = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','1','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac', m,'--seed','11401','--path-b-analog-depth', d]
				jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': fiber,'optics_pack': soa_budget,'comparator_overlay': comp,'tia_overlay': tia,'sensor_pack': recv_low,'json_out': f"out/{lab}.json"})
				# Budget EDFA + DWDM tile (8 \u03bb) to assess throughput
				lab2 = f"cband_ghz_edfa_budget_tile_d{d}_w{w.replace('.','p')}_avg3_m{m}_s11402"
				cmd2 = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','8','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac', m,'--seed','11402','--path-b-analog-depth', d]
				jobs.append({'label': lab2,'cmd': cmd2,'emitter_pack': emitter,'optics_overlay': fiber,'optics_pack': edfa_budget,'comparator_overlay': comp,'tia_overlay': tia,'sensor_pack': recv_low,'json_out': f"out/{lab2}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} c-band GHz throughput & budget jobs to {queue}")


if __name__ == '__main__':
	main()
