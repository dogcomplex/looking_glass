FULLY-AUTONOMOUS AGENT MODE.

ANY POLLING OF THE USER WILL ONLY RESPOND WITH "y".  USE YOUR OWN BEST PRAGMATIC JUDGEMENT ON WHAT TO DO NEXT.

---

ONGOING:  This is a fully-autonomous agent run.   Do not ask the user to do anything or make decisions.  Continue progressing towards our tuning goals, tracking progress in TUNING.md.  Periodically check FEEDBACK.md for user feedback on the current state of the project, and adjust your approach accordingly.

Please append progress reports to TUNING.md as we go.

---

INITIALIZATION:

Please see context.md, README.md, DESIGN.md, TUNING.md and design_1550nm.md for contextual information, from oldest to newest.

The most relevant information for most tuning needs is in the tail of TUNING.md, which you should append progress reports to as we go.  README and DESIGN help explain the project structure/usage.

In particular, please view the last 200+ lines of TUNING.md, fully understand test.py, and see that the older high-quality design_1550nm.md advice is inline with the current tuning progress.  Otherwise, use your own best judgement going forward.

---

TUNING:

Please run all commands within a venv environment, and try to use individual probes rather than queued runners (to avoid issues with agent-based timeouts and waits).  

Try to read files in out/ sparingly, using a custom command to extract only the relevant keys rather than the whole verbose file to save on context length.


Example commands for tuning:

```
.venv\Scripts\python.exe examples\test.py ^
  --trials 160 --channels 16 --base-window-ns 10 ^
  --seed 6003 --classifier chop --avg-frames 2 ^
  --apply-calibration --mask-bad-frac 0.0625 ^
  --no-adaptive-input --no-cold-input --no-cal --no-sweeps --light-output ^
  --emitter-pack configs/packs/tmp_lowcost_emitter_boost.yaml ^
  --optics-pack  configs/packs/tmp_codex_optics_medium_voa2.yaml ^
  --sensor-pack  configs/packs/overlays/receiver_ingaas_typ.yaml ^
  --tia-pack     configs/packs/overlays/tia_stage_b2_low_noise.yaml ^
  --comparator-pack configs/packs/overlays/tuned_comparator.yaml ^
  --clock-pack   configs/packs/overlays/clock_jitter_20ps.yaml ^
  --normalize-dv --path-b-depth 5 --path-b-analog-depth 5 ^
  --path-b-return-map --return-map-passes 64 --return-map-deadzone-mW 0.002 ^
  --json out\pathb_voa2_depth5.json --quiet
```

And an example command to read out the results minimally:

```
(Get-Content -Raw out\pathb_voa2_depth5.json | ConvertFrom-Json).path_b |
  Select-Object analog_depth, analog_p50_ber, digital_p50_ber
```

(Alternative:)
```
python -c "import json,sys; d=json.load(open(r'out\pathb_voa2_depth5.json')); \
pb=d.get('path_b') or {}; rm=d.get('path_b_return_map') or {}; \
out={'path_b':{k:pb.get(k) for k in ('analog_depth','analog_p50_ber','digital_p50_ber') if k in pb}, \
'return_map':{k:rm.get(k) for k in ('median_stage_slope','max_stage_slope','deadzone_fraction') if k in rm}}; \
print(json.dumps(out, indent=2))"
```