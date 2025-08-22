"""
User Clarification and Research Brief Generation

This module implements the scoping phase of the research workflow, where we:
1. Assess if the user's request needs clarification
2. Generate a detailed research brief from the conversation

The workflow uses structured output to make deterministic decisions about
whether sufficient context exists to procees with research.
"""

from datetime import datetime
from typing_extensions import Literal
from typing import List, Dict
from openai import OpenAI
import instructor


# ===== CONFIGURATION =====
client = instructor.from_openai(OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/" , 
                     api_key="AIzaSyB1TdgFNhuPHUqk3-Gzmrn3L5i_l9VjPGw"))


# ===== UTILITY FUNCTIONS =====

def get_today_str() -> str:
    """Get current date in a human-readable format."""
    return datetime.now().strftime("%a %b %-d, %Y")


# 2. Replicate HumanMessage and AIMessage as simple dicts
def human_message(content: str) -> Dict[str, str]:
    return {"role": "user", "content": content}

def ai_message(content: str) -> Dict[str, str]:
    return {"role": "assistant", "content": content}

# 3. Maintain a chat history list
chat_history: List[Dict[str, str]] = []

# 4. Equivalent of get_buffer_string (if you need a plain-text transcript)
def get_buffer_string(history: List[Dict[str, str]]) -> str:
    return "\n".join(f"{msg['role']}: {msg['content']}" for msg in history)

# # -- Usage example --

# # Add a user turn
# chat_history.append(human_message("Hello, how are you?"))

# # Call OpenAI Chat Completion
# response = client.chat.completions.create(
#     model="gemini-2.5-flash",        # or your preferred model
#     temperature=0.7,
#     messages=chat_history,
# )

# # Extract the assistant’s reply
# reply = response. choices[0].message.content

# # Add it to history
# chat_history.append(ai_message(reply))

# # (Optional) print the full back-and-forth
# print(get_buffer_string(chat_history))
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from .prompts import clarify_with_user_instructions, transform_message_into_research_topic_prompt
from .state_scope import AgentState, ClarifyWithUser, ResearchQuestion, AgentInputState
# ===== WORKFLOW NODES =====

def clarify_with_user(state: AgentState) -> Command[Literal["write_research_brief","__end__"]]:
    """
    Determine if the user's request contains sufficient information to proceed with research.

    Uses structured output to make deterministic decisions and avoid hallucination.
    Routes to either research brief generation or ends with a clarification question.
    """
    # Setup structured output model 
    msg = [
            {
            "role": "user",
            "content": clarify_with_user_instructions.format(
                messages=state["messages"],
                date=get_today_str(),
            ),
        },
    ]

    # 2. Call the OpenAI ChatCompletion API
    resp = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=msg,
        temperature=0.0,
        response_model=ClarifyWithUser
    )

    # 3. Parse the raw JSON into our Pydantic model
    raw = resp.choices[0].message.content
    # remove ```json … ``` if present
    # cleaned = raw.strip().removeprefix("```json").removesuffix("```")
    result = ClarifyWithUser.model_validate_json(raw)

    # 4. Branch exactly as before
    if result.need_clarification:
        return Command(
            goto="__end__",
            update={"messages": [{"role":"assistant", "content": result.question}]},
        )
    else:
        return Command(
            goto="write_research_brief",
            update={"messages": [{"role":"assistant", "content": result.verification}]},
        )
    
def write_research_brief(state: AgentState):
    """
    Transform the conversation History into a comprehensive research brief.

    Uses structured output to ensure the brief follows the required format 
    and contains all necessary details for effective research.
    """

    # Setup structured output model 
    msg = [
            {
            "role": "user",
            "content": transform_message_into_research_topic_prompt.format(
                messages=state["messages"],
                date=get_today_str(),
            ),
        },
    ]

    # 2. Call the OpenAI ChatCompletion API
    resp = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=msg,
        temperature=0.0,
        response_model=ResearchQuestion
    )

    # 3. Parse the raw JSON into our Pydantic model
    raw = resp.choices[0].message.content
    # remove ```json … ``` if present
    # cleaned = raw.strip().removeprefix("```json").removesuffix("```")
    result = ResearchQuestion.model_validate_json(raw)

    # Update state with generated research brief and pass it to the supervisor

    return {"research_brief": result.research_brief,
            "supervisor_messages": [{"role":"user","content":result.research_brief}]}

# ===== GRAPH CONSTRUCTION =====

# Build the scoping workflow
deep_research_builder = StateGraph(AgentState, input_schema=AgentInputState)

# Add workflow nodes
deep_research_builder.add_node("clarify_with_user", clarify_with_user)
deep_research_builder.add_node("write_research_brief", write_research_brief)

# Add workflow edges
deep_research_builder.add_edge(START, "clarify_with_user")
deep_research_builder.add_edge("write_research_brief", END)

# Compile the workflow
scope_research = deep_research_builder.compile()