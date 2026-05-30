# Avatar - Spec

## Introduction

Avatar is a new version of an online Digital Twin, with a twist.

It's a web application that allows visitors to a website to interact with a Digital Twin Avatar based on the human that runs the site.

The avatar is implemented using OpenAI Agents SDK, with tools to look up proprietary knowledge.

There's an added dimension: the human (who the twin is representing) can themselves join any of the conversations and weigh in. The conversations are 3-way: between the visitor, the Avatar, and the human.

## User Experiences

### The Interactive Chat Experience

A visitor comes to the web app. They are presented with a modern, sharp, fresh Avatar web app. At the top there is an optional field for them to enter their first name or initials. There's also a switch "Keep chat" that defaults to on.

The browser assigns a unique conversation_id to this chat. If the Keep chat is on, the browser checks cookies to see if this browser has used a unique conversation_id in the past, in which case it uses that (and also calls the server to obtain the chat so far).

There's also a Reset chat button, that clears the chat and assigns a new conversation_id.

The chat is presented as an instant message experience, but more refined that your typical Chatbot screen. The users message have their initials in a bubble. Responding to the user is either the digital twin, or in some cases the human may respond in addition to the Avatar.

### The Human Admin Experience

The human (the owner of this app) can bring up a browser at /admin and enter a password. They are then presented with a dashboard. The left hand sidebar contains a list of conversations (like an email inbox). Most recent on top. They are shown as initials, timestamp, and the beginning of what they said.

When the human clicks on a message in the left hand side bar, the main panel shows the complete interaction with that user and the avatar (and possibly the human). The human can choose to add a message.

It's clear in the Sidebar which messages haven't been read yet. If a message needs the Human's involvement (because the Push tool was used to notify the human) then this is clearly identified (until the human has read the message). Arrow keys can be used to efficiently move up and down the messages, and Enter sends a message (Shift+Enter for a multi-line message).

## Implementation Decisions

- The conversations should be stored in a Supabase database, with conversation_id, timestamp, conversation_name (optional), role, content, and anything to track tool use (future expansion)
- The admin password to use is the environment variable ADMIN_PASSWORD. The backend should have security to ensure that only an authorized user can access other conversations
- The LLM call should use OpenAI Agents SDK. The instructions should explain the full situation. The user prompt (task) should summarize the full conversation so far (i.e. 1 user prompt to handle all roles, rather than user/assistant, because of the human)
- The frontend should poll the backend every 10 seconds for any updates from the human (slowing down to every minute after 5 mins have passed with no activity)
- There is an OpenRouter API key in the .env file. The initial model should be openai/gpt-5.4-mini as specified in MODEL in the .env

### Use of OpenAI Agents SDK

Be absolutely sure to use current, idiomatic treatment of OpenAI Agents SDK. Use their recommended strategy for using OpenRouter instead of OpenAI, per their documentation. Always use idiomatic approaches.

### Tech stack decisions

- The frontend should be an HTML/TS/Vite static site in frontend/
- The backend should be FastAPI with a uv project in a folder backend/ and it should serve the static UI in / and /admin
- The platform should be build as a single Docker container. There should be a scripts/ folder that has a start_mac.sh and stop_mac.sh and start_pc.ps1 and stop_pc.ps1. The start scripts should stop the Docker container if running, then rebuild.
- The platform can be deployed to fly.io (but we won't do that yet).
- The folder knowledge/ has information that should be factored in to its knowledge

### The Reference Files

There are 3 reference files in the reference directory with code examples that you should use:  
1. context.py contains a prompt from a prior Digital Twin. This should be a useful inspiration. But the prompts for the new Avatar will need to be more sophisticated as its a multi-way conversation.
2. next_level.ipynb is a Jupyter Notebook with code to (a) make use of the json FAQ file for quick answers (b) support a shortcut way to ask for a question just by typing "Q2" that doesn't require an LLM call (c) streaming back, including the tool usage. I've not included the CSS but it showed tool use in a small font.
3. push.py shows how to make another tool which will call PushOver to send the Human a notification. This should be used if the visitor wants to get in touch or asks a question that needs a human involvement. If the Avatar can't answer a question, it should use the tool to tell the human and mention in the chat that it's done that.

## UI

The platform must look great in dark mode and light mode.
The palette is:
- Accent Yellow: `#ecad0a` - accent lines, highlights
- Blue Primary: `#209dd7` - links, key sections
- Purple Secondary: `#753991` - submit buttons, important actions
- Dark Navy: `#032147` - main headings
- Gray Text: `#888888` - supporting text, labels

IMPORTANT: Do not have classic LLM tells like gradients, overuse of purple, and the line on the left of panels.
Do not have a standard Chatbot style.
The look must be sharp, compelling, exciting, modern.
Vector symbols are great where useful; but strictly no emojis.

Ensure that the chat message field takes focus for the user when they bring up the page, and that it regains focus after sending a message (by clicking or by hitting enter).

The image in knowledge/pic.jpg should be used for the Avatar icon for the Human, and a robotic version of it should be used as the Avatar icon for the Avatar, looking like a Digital Twin of the human.

## Testing

Testing is absolutely crucial for the success of this project.

1. Test the backend thoroughly with comprehensive unit tests, including tests to ensure that admin api routes are only available if logged in
2. Rigorously test the frontend. Use Playwright, take multiple screenshots. Ensure everything works in significant detail.
3. Build the Docker container and test everything end to end; very comprehensively

You should write comprehensive test plans for each of these, document the test plans in the test/ directory with checkboxes, and then check them off.

NOTE: It's good to use the model and pushover as part of your testing, but change the model to gpt-5.4-nano to reduce costs. Then it's fine to call the LLM for tests and to write test conversations in the Supabase database. There are sensible rate limits on the OpenRouter key; you can use it as much as you wish.

When you've completed testing, delete the screenshots and delete the test conversation threads in Supabase, and check off the items in your test plans.

## Success Criteria

The project is only successful when you can run the script to build the container, then run the application end-to-end, carry out full testing with the user, avatar and human participating (and multiple users with different conversation_ids). The tests should include multiple screenshots. The tests should be fully documented in the test/ folder. Only conclude the project when your extensive testing is completed and working well and looking great.