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
	soa_budget = 'configs/packs/overlays/soa_chain_budget.yaml'
	edfa_budget = 'configs/packs/overlays/edfa_chain_budget.yaml'

	# 1) Back-reflection spike stress, single-λ SOA at 6 ns, depth 12
	lab1 = 'cband_mf_refl_soa_d12_w6p0_s11601'
	cmd1 = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','1','--base-window-ns','6.0','--avg-frames','3','--mask-bad-frac','0.05','--seed','11601','--path-b-analog-depth','12']
	jobs.append({'label': lab1,'cmd': cmd1,'emitter_pack': emitter,'optics_overlay': fiber,'optics_pack': soa_budget,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab1}.json"})

	# 2) λ drift across AWG slope: emulate by setting higher dwdm_slope and add temp change via emitter drift
	lab2 = 'cband_mf_ldrift_edfa_tile_d10_w6p0_s11602'
	cmd2 = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','8','--base-window-ns','6.0','--avg-frames','3','--mask-bad-frac','0.05','--seed','11602','--path-b-analog-depth','10']
	jobs.append({'label': lab2,'cmd': cmd2,'emitter_pack': emitter,'optics_overlay': fiber,'optics_pack': edfa_budget,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab2}.json"})

	# 3) Worst-case isolation DWDM + high total launch power (tile)
	lab3 = 'cband_mf_xtalk_tile_d10_w6p0_s11603'
	cmd3 = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','8','--base-window-ns','6.0','--avg-frames','3','--mask-bad-frac','0.05','--seed','11603','--path-b-analog-depth','10']
	job3 = {'label': lab3,'cmd': cmd3,'emitter_pack': emitter,'optics_overlay': 'configs/packs/overlays/dwdm_crosstalk_ripple.yaml','optics_pack': edfa_budget,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab3}.json"}
	jobs.append(job3)

	# Follow-up passes can be added with calibration flags once hooks exist

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} c-band must-fail tests to {queue}")


if __name__ == '__main__':
	main()
