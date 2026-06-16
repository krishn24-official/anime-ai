from fastapi import APIRouter
from pydantic import BaseModel

from app.services.agent_service import run_agent

router = APIRouter(
    prefix="/agent",
    tags=["Agent"]
)


class AgentRequest(BaseModel):
    message: str


@router.post("")
async def agent(payload: AgentRequest):
    """
    Agentic AI endpoint. The agent can call multiple tools (birthdays,
    news, search, character info) to answer complex multi-step questions.

    Example questions:
    - "Which characters have birthdays today and is there any news about them?"
    - "What's the latest anime news?"
    - "Tell me everything about Naruto Uzumaki"
    - "Are there any anime anniversaries today?"
    - "What movies are in the database and what are their ratings?"
    """
    return await run_agent(payload.message)