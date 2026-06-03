---
name: openai-mcp
description: How to equip an agent in OpenAI Agents SDK with an MCP Server
---

## Summary

OpenAI Agents SDK makes it easy and convenient to equip your agent with an MCP server.
In the majority of cases, MCP servers use stdio.

## Simple example

Here's an example:

```
from agents import Agent, Runner
from agents.mcp import MCPServerStdio
params = {"command": "uvx", "args": ["mcp-server-fetch"]}

INSTRUCTIONS = "You use your tools to browse the internet and answer questions."
TASK = "Please summarize the content of www.edwarddonner.com"

async def example():
  async with MCPServerStdio(params, client_session_timeout_seconds=240) as server:
      agent = Agent("Fetcher", model="gpt-5.4-mini", instructions=INSTRUCTIONS, mcp_servers=[server])
      response = await Runner.run(agent, TASK, max_turns=30)
      print(response.final_output)
```

Potential gotchas:
- Ensure the client_session_timeout_seconds is long enough, because if the package isn't in uv's cache then it will need to download
- Ensure sufficient max_turns
- Beware when deploying in docker containers that you'll need to test whether the MCP server will work; uv will need to be installed and it will need to be tested carefully. A potential workaround to problems is to run "uv tool install mcp-server-fetch" in the Dockerfile to pre-install the package and then change the parameters to "mcp-server-fetch".

## Other popular stdio MCP servers

vectorstore_params = {
    "command": "uvx",
    "args": ["mcp-server-qdrant"],
    "env": {
        "QDRANT_LOCAL_PATH": str(vectordb_path),
        "COLLECTION_NAME": "knowledge",
    },
}

## Using Streamable HTTP MCP servers (not as common)

```
task = "Why did Streamable HTTP replace the older SSE for remote MCP servers?"


params = {"url": "https://mcp.context7.com/mcp", "timeout": 60}


async with MCPServerStreamableHttp(name="Context7", params=params) as server:
    agent = Agent(name="Expert", instructions="Use Context7 to answer the question", mcp_servers=[server], model="gpt-5.4-mini")
    result = await Runner.run(agent, task)

print(result.final_output)
```

## For more information

Read the OpenAI SDK docs on MCP servers here: https://openai.github.io/openai-agents-python/mcp/
But ignore the parts about Hosted MCP servers as that's not common, and SSE servers as they are legacy.
