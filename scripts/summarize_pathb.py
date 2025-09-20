import json, sys

def pick(d, keys):
    return {k: d.get(k) for k in keys if k in d}

def summarize(path):
    d = json.load(open(path, 'r'))
    pb = d.get('path_b') or {}
    rm = d.get('path_b_return_map') or {}
    out = {
        'file': path,
        'path_b': pick(pb, ['analog_depth','analog_p50_ber','digital_p50_ber','tdm_symbols_per_s','tdm_micro_passes','tdm_recenter_events','tdm_recenter_duty']),
        'return_map': pick(rm, ['median_stage_slope','max_stage_slope'])
    }
    print(json.dumps(out, indent=2))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: python scripts/summarize_pathb.py <json> [<json> ...]')
        sys.exit(1)
    for p in sys.argv[1:]:
        summarize(p)
