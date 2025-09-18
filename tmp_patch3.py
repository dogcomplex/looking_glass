from pathlib import Path
text = Path('examples/test.py').read_text(encoding='utf-8')
needle = "                ratio = _np.abs(diff_out) / _np.clip(_np.abs(diff_in), eps, None)\n                level_slopes[stage].append(float(_np.median(ratio)))\n                level_dead[stage].append(float(_np.mean(_np.abs(diff_out) < deadzone_mw)))\n"
replacement = "                ratio = _np.abs(diff_out) / _np.clip(_np.abs(diff_in), eps, None)\n                level_slopes[stage].append(float(_np.median(ratio)))\n                level_dead[stage].append(float(_np.mean(_np.abs(diff_out) < deadzone_mw)))\n                level_diff_in[stage].append(float(_np.median(_np.abs(diff_in))))\n                level_diff_out[stage].append(float(_np.median(_np.abs(diff_out))))\n"
if 'level_diff_in[stage].append' not in text:
    text = text.replace(needle, replacement)
    Path('examples/test.py').write_text(text, encoding='utf-8')
