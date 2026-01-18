"""Prompt version management — history, diff view, activate."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_prompts():
    return {"prompts": []}


@router.get("/{prompt_hash}")
async def get_prompt(prompt_hash: str):
    return {"prompt": None}


@router.post("/activate/{prompt_hash}")
async def activate_prompt(prompt_hash: str):
    """Deactivate current prompt, activate specified version."""
    return {"status": "activated", "hash": prompt_hash}
