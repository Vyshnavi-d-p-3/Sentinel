"""Eval endpoints — run history, per-category metrics, prompt version comparison."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/runs")
async def list_eval_runs():
    return {"runs": []}


@router.get("/runs/{run_id}")
async def get_eval_run(run_id: str):
    return {"run": None}


@router.get("/compare")
async def compare_prompts(prompt_a: str, prompt_b: str):
    """Side-by-side comparison of two prompt versions across all categories."""
    return {"comparison": None}


@router.post("/trigger")
async def trigger_eval():
    """Manually trigger eval run (also runs in CI via GitHub Actions)."""
    return {"status": "triggered"}
