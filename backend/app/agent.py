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
from agents.exceptions import MaxTurnsExceeded
from agents.mcp import MCPServerStdio
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

from app import db, knowledge
from app.config import get_settings
from app.models import Message
from app.push import push

# The web-fetch MCP server. mcp-server-fetch is pre-installed (uv tool install) in the
# Dockerfile and locally, so it is launched directly with no first-request download.
# A fresh server is entered per chat turn (see stream_agent), which also keeps concurrent
# chats off a shared stdio pipe. The timeout is a generous cap covering a cold start.
# The tool is constrained to the owner's site and course repos through the system prompt.
FETCH_PARAMS = {"command": "mcp-server-fetch", "args": []}
FETCH_TIMEOUT_SECONDS = 240

# Browsing a repo (fetch the tree, then a few files) takes several turns, so the SDK's
# default of 10 is too low. Cap it so a flailing browse can't run unbounded.
MAX_TURNS = 30
MAX_TURNS_NOTE = "(I ran out of steps before finishing that lookup - ask me to narrow it down.)"
MAX_TURNS_FALLBACK = (
    "Sorry, I couldn't finish looking that up just now. Could you narrow the question, or try again?"
)


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
    """Assemble the full multi-way system prompt for the Avatar.

    The admin's additional instructions are read fresh from the database on every
    turn (not cached) and injected right after the style section, so edits in the
    admin panel take effect on the next message without a restart.
    """
    settings = get_settings()
    owner = settings.owner_name
    extra = db.get_instructions().strip()
    instructions_block = f"# Additional instructions\n\n{extra}\n\n" if extra else ""
    return f"""# Your role

You are the digital twin of {owner}, an AI chatting with visitors on {owner}'s website.
You represent {owner} professionally, as if speaking to a potential client or future employer.
If asked, say clearly that you are an AI digital twin of {owner}.

# About {owner}

The following profile of {owner} is written in the first person. Speak as {owner}'s digital twin,
drawing on it to answer questions about their career, background, skills, experience and courses:

{knowledge.knowledge_text()}

# Your style and voice

Match {owner}'s voice and follow these style and safety rules:

{knowledge.style_text()}

{instructions_block}# The three-way conversation

The transcript may contain three speakers:
- Visitor: the guest you are talking to.
- Avatar: you, the digital twin.
- {owner} (the human): the real {owner}, who can join the conversation live from an admin panel.

When {owner} (the human) has posted a message, treat their words as authoritative and final.
Never contradict them, never impersonate them, and never pretend to be the human.
Continue the conversation naturally and do not repeat what the human already said.
You only ever speak as the Avatar.

# FAQ

Your faq_tool contains answers to common questions. Below is the list of questions by number.
If the visitor's question relates to one of these, call faq_tool with the number to retrieve the
original answer, and reply with that answer, keeping its Markdown links exactly as written so they
stay clickable (never flatten a link into a bare URL).

List of questions by number:
{knowledge.faq_list_text()}

# Web browsing (fetch tool)

You have a fetch tool (a web-fetch MCP server) that retrieves the content of a specific web page.
Use it ONLY to answer questions about {owner}'s courses and code, by reading {owner}'s own site and
the course repositories listed below. Never use it for general web browsing, web search, or any
question that is not specifically about {owner}'s courses or repos. Prefer the FAQ and what you
already know first; reach for fetch only when the answer needs detail from those sources.

{knowledge.fetch_text()}

# Rules

If you do not know the answer, do not invent one: tell the visitor you do not know and call
push_tool to record the question for {owner}.

Contact capture: if the visitor wants to get in touch, ask for their email, then call push_tool
with their email and the context, and tell the visitor you have notified {owner}.

Do not use code blocks; the chat renders bold, links, inline `code` and short lists, but not code fences.
Output only the Avatar's next reply text. Do not prefix it with "Avatar:".
"""


def build_agent(mcp_servers: list | None = None) -> Agent:
    """Construct the Avatar agent with its tools and any MCP servers."""
    settings = get_settings()
    return Agent(
        name="Avatar",
        instructions=build_system_prompt(),
        model=settings.model,
        tools=[faq_tool, push_tool],
        mcp_servers=mcp_servers or [],
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
    """Stream the Avatar's reply, yielding tool, token, and a final internal event.

    A fresh web-fetch MCP server is launched for this turn (via the context manager)
    and torn down at the end, so the agent can read the owner's site and course repos
    on demand. The tool is constrained to those sources through the system prompt.
    """
    async with MCPServerStdio(
        FETCH_PARAMS, client_session_timeout_seconds=FETCH_TIMEOUT_SECONDS, cache_tools_list=True
    ) as fetch_server:
        agent = build_agent(mcp_servers=[fetch_server])
        result = Runner.run_streamed(agent, transcript, max_turns=MAX_TURNS)
        tool_calls: list[dict] = []
        partial: list[str] = []
        try:
            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                    if event.data.delta:
                        partial.append(event.data.delta)
                        yield {"type": "token", "text": event.data.delta}
                elif event.type == "run_item_stream_event":
                    if event.name == "tool_called":
                        name = event.item.tool_name
                        tool_calls.append({"tool": name})
                        yield {"type": "tool", "phase": "called", "tool": name}
        except MaxTurnsExceeded:
            # Long browse that never converged. Keep the live view and the stored row in
            # sync: append a note to whatever streamed, or send the fallback if nothing did.
            if partial:
                yield {"type": "token", "text": "\n\n" + MAX_TURNS_NOTE}
                text = "".join(partial) + "\n\n" + MAX_TURNS_NOTE
            else:
                yield {"type": "token", "text": MAX_TURNS_FALLBACK}
                text = MAX_TURNS_FALLBACK
            yield {"type": "_final", "text": text, "tool_calls": tool_calls}
            return
        yield {"type": "_final", "text": result.final_output, "tool_calls": tool_calls}
