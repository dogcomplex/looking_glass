from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from looking_glass.scenario import build_orchestrator_from_scenario


def test_build_orchestrator_without_optional_packs():
    scenario_path = repo_root / "configs" / "scenarios" / "pd_only.yaml"

    orch, trials, scn = build_orchestrator_from_scenario(scenario_path)

    assert trials == 5
    assert "camera_pack" not in scn
    assert "thermal_pack" not in scn

    # Optional packs should not be instantiated when missing from the scenario
    assert orch.cam is None
    assert orch.therm is None

    # A single step should execute without raising even without optional packs
    result = orch.step()
    assert "ber" in result
    assert "energy_pj" in result
