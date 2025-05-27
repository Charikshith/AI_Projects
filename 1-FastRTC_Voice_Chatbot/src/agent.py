import asyncio
from loguru import logger
import uuid

# ADK imports
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.adk.runners import Runner

# Original tool functions (can be kept as is)
# ADK will use their docstrings as descriptions for the LLM.
def sum_numbers(a: float, b: float) -> float:
    """Sum two numbers together."""
    result = a + b
    logger.info(f"➕ Calculating sum: {a} + {b} = {result}")
    return result


def multiply_numbers(a: float, b: float) -> float:
    """Multiply two numbers together."""
    result = a * b
    logger.info(f"✖️ Calculating product: {a} × {b} = {result}")
    return result


# Application Name Constant
APP_NAME = "Alferd Bot"

# 1. Define the LLM for ADK
# Make sure your GROQ_API_KEY environment variable is set.
# The model name "llama-4-scout-17b-16e-instruct" (used here as "groq/llama-4-scout-17b-16e-instruct")
# might be a custom or internal model name. Please ensure it's a valid model accessible via your Groq API key.
# If not, replace it with a standard Groq model like "llama3-8b-8192".
adk_llm_model = LiteLlm(
    model="groq/llama-3.1-8b-instant",
    
)

# 2. Define Tools for ADK
# ADK tools are created from functions. The docstrings are used for descriptions.
adk_tools= [
    sum_numbers,multiply_numbers,
]

# 3. Define System Prompt / Instructions for ADK Agent
system_instructions = """You are Samantha, a helpful math assistant with a warm personality.
You can help with basic math operations by using your tools.
Always use the tools when asked to do math calculations.
Your output will be converted to audio so avoid using special characters or symbols.
Keep your responses friendly and conversational."""

# 4. Create the ADK ReAct Agent
samantha_adk_agent = Agent(
    name="samantha_math_agent",
    model=adk_llm_model,
    tools=adk_tools,
    instruction=system_instructions,
    # verbose=True  # Optional: for more detailed logging from the agent's internal steps
)

# 5. Interacting with the Agent using ADK Dispatcher
# The Dispatcher helps manage sessions and routes requests to agents.
# InMemorySessionManager is suitable for non-persistent, in-memory session state.
mem_session_manager = InMemorySessionService()

runner = Runner(agent=samantha_adk_agent,app_name=APP_NAME,session_service=mem_session_manager)

async def chat_with_samantha(
    query: str,
    runner_instance: Runner,
    user_id: str,
    session_id: str
):
    """
    Sends a query to the agent for a specific user and session,
    and prints the final response.
    """

    print(f"\n>>> User Query (User: {user_id}, Session: {session_id}): {query}")
    # Prepare the user's message in ADK format
    content = types.Content(role='user', parts=[types.Part(text=query)])

    final_response_text = "Agent did not produce a final response." # Default
    
    # Key Concept: run_async executes the agent logic and yields Events.
    # We iterate through events to find the final answer.
    async for event in runner_instance.run_async(user_id=user_id, session_id=session_id, new_message=content):
        # You can uncomment the line below to see *all* events during execution
        # print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")
        # Key Concept: is_final_response() marks the concluding message for the turn.
        if event.is_final_response():
            if event.content and event.content.parts:
                # Assuming text response in the first part
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate: # Handle potential errors/escalations
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            # Add more checks here if needed (e.g., specific error codes)
            break # Stop processing events once the final response is found

    print(f"<<< Agent Response (User: {user_id}, Session: {session_id}): {final_response_text}")
    return final_response_text

agent_config = {"configurable": {"thread_id": "default_user"}}

async def main():
    # Example conversations
    # Note: For this to run, you need:
    # 1. `agent-development-kit[groq]` installed (e.g., pip install agent-development-kit[groq])
    # 2. GROQ_API_KEY environment variable set with your Groq API key.

    # --- Conversation 1 (user_1, session_1) ---
    user_1_id = "math_enthusiast_001"
    session_1_id = str(uuid.uuid4())
    mem_session_manager.create_session(app_name=APP_NAME, user_id=user_1_id, session_id=session_1_id)
    logger.info(f"Created new session {session_1_id} for user {user_1_id}")

    await chat_with_samantha(
        query="Hi Samantha, can you sum 3 and 5 for me?",
        runner_instance=runner,
        user_id=user_1_id,
        session_id=session_1_id
    )
    # Continue conversation 1 in the same session
    await chat_with_samantha(
        query="Great! Now, what is 4 multiplied by 7?",
        runner_instance=runner,
        user_id=user_1_id, # Same user
        session_id=session_1_id # Same session
    )

    # Example of a new, separate conversation
    # --- Conversation 2 (user_2, session_2) ---
    user_2_id = "curious_learner_002"
    session_2_id = str(uuid.uuid4())
    mem_session_manager.create_session(app_name=APP_NAME, user_id=user_2_id, session_id=session_2_id)
    logger.info(f"Created new session {session_2_id} for user {user_2_id}")
    await chat_with_samantha(
        query="What is 100 plus 200?",
        runner_instance=runner,
        user_id=user_2_id,
        session_id=session_2_id
    )

if __name__ == "__main__":
    asyncio.run(main())
