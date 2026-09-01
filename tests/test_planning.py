from pathlib import Path

from skynet.planning import PlanStore


def test_plan_lifecycle(tmp_path: Path) -> None:
    store = PlanStore(tmp_path / "plans")
    plan = store.create("Test task", ["Inspect", "Act", "Verify"])
    assert len(plan.steps) == 3
    updated = store.update(plan.id, 1, "done", "inspection ok")
    assert updated.steps[0].status == "done"
    reloaded = store.read(plan.id)
    assert reloaded.steps[0].evidence == "inspection ok"
