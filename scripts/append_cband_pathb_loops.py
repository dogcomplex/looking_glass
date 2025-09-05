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
	soa = 'configs/packs/overlays/soa_chain_soft.yaml'
	edfa = 'configs/packs/overlays/edfa_chain_typ.yaml'

	depths = ['1','2','3','4','5','6']
	windows = ['12.0','16.0','19.0']
	modes = [
		('soa', soa),
		('edfa', edfa),
	]
	for tag, gain in modes:
		for d in depths:
			for w in windows:
				label = f"cband_pathb_{tag}_d{d}_w{w.replace('.','p')}_avg3_m0.09375_s11101"
				cmd = [
					'--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input',
					'--classifier','chop','--channels','1','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac','0.09375',
					'--seed','11101','--path-b-analog-depth', d,
				]
				jobs.append({'label': label,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': fiber,'comparator_overlay': comp,'tia_overlay': tia,'optics_pack': gain,'json_out': f"out/{label}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} c-band Path B loop jobs to {queue}")


if __name__ == '__main__':
	main()
