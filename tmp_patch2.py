from pathlib import Path
text = Path('examples/test.py').read_text(encoding='utf-8')
marker = "        level_slopes = [[] for _ in range(depth)]\n        level_dead = [[] for _ in range(depth)]\n        level_pos = [[] for _ in range(depth)]\n        level_neg = [[] for _ in range(depth)]\n"
addition = "        level_slopes = [[] for _ in range(depth)]\n        level_dead = [[] for _ in range(depth)]\n        level_pos = [[] for _ in range(depth)]\n        level_neg = [[] for _ in range(depth)]\n        level_diff_in = [[] for _ in range(depth)]\n        level_diff_out = [[] for _ in range(depth)]\n"
if 'level_diff_in' not in text:
    text = text.replace(marker, addition)
    Path('examples/test.py').write_text(text, encoding='utf-8')
