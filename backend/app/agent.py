"""The Avatar agent: OpenRouter wiring, tools, system prompt, and streaming.

The conversation is three-way (visitor, avatar, human). The transcript is
rendered into a single task string passed to the agent; the agent always
replies only as the Avatar.
"""

from collections.abc import AsyncIterator

from agents import (
    Agent,
    Runner,
    function_tool,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

from app import knowledge
from app.config import get_settings
from app.models import Message
from app.push import push


def configure_openrouter() -> None:
    """Point the Agents SDK at OpenRouter using the chat-completions API."""
    settings = get_settings()
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )
    set_default_openai_client(client)
    set_default_openai_api("chat_completions")
    set_tracing_disabled(True)


@function_tool
def faq_tool(number: int) -> str:
    """Look up the answer to a frequently asked question by its number.

    Args:
        number: The FAQ number to retrieve.
    """
    return knowledge.find_faq(number)


@function_tool
def push_tool(message: str) -> str:
    """Send a push notification to the human owner (your human twin) so they can follow up.

    Args:
        message: The note to send to the human owner.
    """
    return push(message)


def build_system_prompt() -> str:
    """Assemble the full multi-way system prompt for the Avatar."""
    settings = get_settings()
    owner = settings.owner_name
    return f"""# Your role

You are the digital twin of {owner}, an AI chatting with visitors on {owner}'s website.
You represent {owner} professionally, as if speaking to a potential client or future employer.
If asked, say clearly that you are an AI digital twin of {owner}.

Here are the details of {owner}:

{knowledge.summary_text()}

# The three-way conversation

The transcript may contain three speakers:
- Visitor: the guest you are talking to.
- Avatar: you, the digital twin.
- {owner} (the human): the real {owner}, who can join the conversation live from an admin panel.

When {owner} (the human) has posted a message, treat their words as authoritative and final.
Never contradict them, never impersonate them, and never pretend to be the human.
Continue the conversation naturally and do not repeat what the human already said.
You only ever speak as the Avatar.

# Background

Here is {owner}'s LinkedIn profile so you can answer questions about career and experience:

{knowledge.linkedin_text()}

# FAQ

Your faq_tool contains answers to common questions. Below is the list of questions by number.
If the visitor's question relates to one of these, call faq_tool with the number to retrieve the
original answer, and reply with that answer preserving its markdown links.

List of questions by number:
{knowledge.faq_list_text()}

# Rules

Answer questions about {owner}'s career, background, skills, experience, and courses.
Be professional and engaging. If asked about something unrelated, steer back to professional topics.

Contact capture: if the visitor wants to get in touch, ask for their email, then call push_tool
with their email and the context, and tell the visitor you have notified {owner}.

If you do not know the answer, call push_tool to record the question for {owner}, then tell the
visitor you do not know and have flagged it for {owner}. Never invent an answer.

Use engaging markdown (bold, links, short lists) but no code blocks. Be concise.
Output only the Avatar's next reply text. Do not prefix it with "Avatar:".
"""


def build_agent() -> Agent:
    """Construct the Avatar agent with its tools."""
    settings = get_settings()
    return Agent(
        name="Avatar",
        instructions=build_system_prompt(),
        model=settings.model,
        tools=[faq_tool, push_tool],
    )


def render_transcript(rows: list[Message], owner_name: str) -> str:
    """Render prior messages as labelled lines, ending with a reply instruction."""
    lines = []
    for row in rows:
        if row.role == "visitor":
            lines.append(f"Visitor: {row.content}")
        elif row.role == "avatar":
            lines.append(f"Avatar: {row.content}")
        else:
            lines.append(f"{owner_name} (the human): {row.content}")
    transcript = "\n".join(lines)
    return f"{transcript}\n\nReply as the Avatar:"


async def stream_agent(transcript: str) -> AsyncIterator[dict]:
    """Stream the Avatar's reply, yielding tool, token, and a final internal event."""
    agent = build_agent()
    result = Runner.run_streamed(agent, transcript)
    tool_calls: list[dict] = []
    async for event in result.stream_events():
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            if event.data.delta:
                yield {"type": "token", "text": event.data.delta}
        elif event.type == "run_item_stream_event":
            if event.name == "tool_called":
                name = event.item.tool_name
                tool_calls.append({"tool": name})
                yield {"type": "tool", "phase": "called", "tool": name}
    yield {"type": "_final", "text": result.final_output, "tool_calls": tool_calls}
