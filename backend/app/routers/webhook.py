"""GitHub webhook handler — validates HMAC, routes PR events to orchestrator."""

from fastapi import APIRouter, Request, HTTPException, Header
from app.core.security import verify_webhook_signature

router = APIRouter()


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(...),
    x_github_event: str = Header(...),
):
    """Receive and validate GitHub webhook events."""
    payload = await request.body()

    if not verify_webhook_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}

    # TODO: Parse PR payload, trigger ReviewOrchestrator.review_pr()
    return {"status": "accepted"}
