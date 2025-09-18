from pathlib import Path
text = Path('examples/test.py').read_text(encoding='utf-8')
needle = "        results[\"stage_slopes\"].append([float(_np.median(s)) if s else None for s in level_slopes])\n        results[\"deadzone_fraction\"].append([float(_np.median(d)) if d else None for d in level_dead])\n        results[\"rail_positive_fraction\"].append([float(_np.median(r)) if r else None for r in level_pos])\n        results[\"rail_negative_fraction\"].append([float(_np.median(r)) if r else None for r in level_neg])\n"
replacement = "        results[\"stage_slopes\"].append([float(_np.median(s)) if s else None for s in level_slopes])\n        results[\"deadzone_fraction\"].append([float(_np.median(d)) if d else None for d in level_dead])\n        results[\"rail_positive_fraction\"].append([float(_np.median(r)) if r else None for r in level_pos])\n        results[\"rail_negative_fraction\"].append([float(_np.median(r)) if r else None for r in level_neg])\n        results[\"stage_diff_in\"].append([float(_np.median(di)) if di else None for di in level_diff_in])\n        results[\"stage_diff_out\"].append([float(_np.median(do)) if do else None for do in level_diff_out])\n"
if 'stage_diff_in' not in text:
    text = text.replace(needle, replacement)
    Path('examples/test.py').write_text(text, encoding='utf-8')
