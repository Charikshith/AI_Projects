"""State Definitions and Pydantic Schemas for Research Scoping.

This defines the state objects and structured schemas used for the research agent scoping workflow, including researcher state 
management and output schemas"""

import operator
from typing import Optional, Annotated, List, Sequence, Literal

# from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A minimal chat-message format, compatible with OpenAI roles."""
    role: Literal["system", "user", "assistant"]
    content: str

# ======= STATE DEFINITIONS=======

class AgentInputState(MessagesState):
    """Input state for the fill agent - only contains message from user input"""
    pass

class AgentState(MessagesState):
    """
    Main state for the full multi-agent research system.

    Extends MessageState with additional fields for research coordination.
    Note: Some fields are duplicated across different state classes for proper state
    management between subgraphs and the main workflow.
    """

    # Research brief generated from user conversation history
    research_brief: Optional[str]

    # MEssages exchanged with the supervisor agent for coordination
    supervisor_messages: Annotated[Sequence[ChatMessage],add_messages]
    # Raw unprocessed research note collected during the research phase
    raw_notes: Annotated[list[str],operator.add] = []
    # Processed and structured notes ready for report generation
    notes: Annotated[list[str], operator.add] = []
    # Final formatted research report
    final_report: str


class ClarifyWithUser(BaseModel):
    """Schema for user clarification decision and questions."""

    need_clarification: bool = Field(description="Whether the user needs to be asked a clarifying question.")
    question: str = Field(description=" A question to ask the user to clarify the report scope.")
    verification: str = Field(description=" Verify message that we will start research after the user has provided necessary information.")

class ResearchQuestion(BaseModel):
    """Schema for structured research brief generatioon."""
    research_brief: str = Field(description=" A research question that will be used to guide the research.")