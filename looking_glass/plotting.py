from __future__ import annotations

from pathlib import Path
import typing as t


def save_xy_plot(x: t.Sequence[float],
                 y: t.Sequence[float],
                 xlabel: str,
                 ylabel: str,
                 out_path: str | Path,
                 title: str | None = None) -> bool:
    """Save a simple line plot to a PNG. Returns True if saved, False if matplotlib is missing.

    This function avoids hard dependency on matplotlib; if unavailable, it returns False.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except (ModuleNotFoundError, RuntimeError):
        return False

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=120)
    ax.plot(x, y, marker="o")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return True

