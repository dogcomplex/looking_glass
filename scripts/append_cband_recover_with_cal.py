from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	fiber_typ = 'configs/packs/overlays/fiber_cband_loop_typ.yaml'
	fiber_stress = 'configs/packs/overlays/fiber_cband_loop_stress.yaml'
	comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
	tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
	soa_budget = 'configs/packs/overlays/soa_chain_budget.yaml'
	edfa_budget = 'configs/packs/overlays/edfa_chain_budget.yaml'

	# Recovery knobs: normalization + lite gating + small averaging + masking + Vth auto-zero
	recover_flags = [
		'--classifier','chop',
		'--normalize-dv','--normalize-eps-v','1e-6',
		'--avg-frames','3','--use-avg-frames-for-path-a',
		'--gate-thresh-mV','0.6',
		'--mask-bad-frac','0.05',
		'--apply-calibration'
	]

	# Mirror test 1 (SOA reflection) with recovery flags
	lab1 = 'cband_recover_refl_soa_d12_w6p0_s11611_v3'
	cmd1 = ['--trials','600','--no-sweeps','--light-output','--channels','1','--base-window-ns','6.0','--seed','11611','--path-b-analog-depth','12'] + recover_flags
	jobs.append({'label': lab1,'cmd': cmd1,'emitter_pack': emitter,'optics_overlay': fiber_stress,'optics_pack': soa_budget,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab1}.json"})

	# Mirror test 2 (EDFA λ drift tile) with recovery flags
	lab2 = 'cband_recover_ldrift_edfa_tile_d10_w6p0_s11612_v3'
	cmd2 = ['--trials','600','--no-sweeps','--light-output','--channels','8','--base-window-ns','6.0','--seed','11612','--path-b-analog-depth','10'] + recover_flags
	jobs.append({'label': lab2,'cmd': cmd2,'emitter_pack': emitter,'optics_overlay': fiber_stress,'optics_pack': edfa_budget,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab2}.json"})

	# Mirror test 3 (DWDM crosstalk+ripple tile) with recovery flags
	lab3 = 'cband_recover_xtalk_tile_d10_w6p0_s11613_v3'
	cmd3 = ['--trials','600','--no-sweeps','--light-output','--channels','8','--base-window-ns','6.0','--seed','11613','--path-b-analog-depth','10'] + recover_flags
	jobs.append({'label': lab3,'cmd': cmd3,'emitter_pack': emitter,'optics_overlay': 'configs/packs/overlays/dwdm_crosstalk_ripple.yaml','optics_pack': edfa_budget,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab3}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} c-band recovery tests to {queue}")


if __name__ == '__main__':
	main()
