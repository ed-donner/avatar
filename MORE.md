# Building Additional Functionality

For the next evolution of the Digital Twin, here are some enhancements.
Please note: you should never deploy to production; only ever work locally, deploying to the local docker.

IMPORTANT NOTE:

Also note: there only is one Supabase database, and it's production. Only archive messages that you create. Be very careful when you're testing so that you don't accidentally delete actual user conversations in flight. It would be worth saving all conversations so far locally just as a protection in case anything goes wrong.

After all changes are implemented, the Admin will have a main nav for 4 sections:

Conversations | Archive | Instructions | FAQ

## Archive functionality

There should be another database table called archive with the same structure as conversations.
The admin user should have an archive button on each message to click to archive it.
Archiving a conversation adds the conversation to the archive table, and then deletes it from the conversations table.
There should also be a button on the Admin screens "Archive all conversations with no activity in 72 hours".
The Admin screens should have a main nav with the ability to switch to the Archive Conversations. From there, you can see the entire list of Archived conversations. It should be possible to restore a conversation.
All these operations should apply to an entire conversation.

## Download button and Total

On both the "Conversations" page and the "Archive" page, there should also be a Download button, that downloads all the conversations / archive to a jsonl file locally. Also somewhere near the top each page should state the total number of conversations or archive conversations.

## Polling frequency

Check the current approach for the visitor screens polling. Make it so that:
It polls for Ed messages every 10 seconds after each message.
If no messages for 2 mins, it starts polling every 30 seconds.
If no messages for 10 mins, it starts polling every 2 mins.
If no messages for 1 hour, it starts polling every 5 mins.

That will reduce the level of activity on the server.

## Additional prompt instructions

The admin dashboard main nav, in addition to having Conversations and Archive, should also have a section for addiitonal instructions.
This should have a freeform field containing Markdown stored in the Supabase database.
The existing value should be shown to the admin, empty initially, and additional markdown can be added by the admin and saved.
This is appended to the prompt as part of the system prompt after the style section.

## Move FAQ to Supabase

The FAQ jsonl should be moved to be a Supabase table (with id, concise, question and answer as 4 columns).
There should be an editor in the UI to update, delete, add questions.
When uploading the FAQ to Supabase, note that there are some problems with it: there are cases where OPENAI_API_KEY needs to have markdown code blocks like `OPENAI_API_KEY` otherwise the underscores appear as emphasis highlights.
Also Q50 incorrectly references an image.
Check that the other questions are all appropriate for this purpose.

## Web Fetch with MCP for edwarddonner.com and for course repos

Use your openai-mcp skill to build this.
See the reference implementation in reference/fetch.ipynb.
Add this web server functionality to the Agent via the fetch MCP server, including something similar to the given INSTRUCTIONS in the reference. Ensure that the agent doesn't use this for generic web searching through prompting, just as described in the reference implementation.
Ensure that the use of fetch MCP tool is shown in the UI, along with the faq tool and push tool.

## Generate image for social icons, for when the Avatar link is pasted into LinkedIn / etc

I'd like to add og social icons to the Avatar webpage on my wordpress site. Please create an appropriately sized file and save it as og-avatar in the project root.

## Support another query parameter

It should be possible to pass in a question like this:

localhost:8000/m=whats+the+price+of+sliced+bread

And that will be entered (and return key pressed) automatically as a message to the avatar.
If necessary, let me know if I need to change the snippet in Wordpress to support the passthrough, but this is what's there now and it looks good to me:

```
<div id="avatar-embed">
    <iframe id="avatar-frame" title="Ed Donner's Digital Twin" referrerpolicy="strict-origin-when-cross-origin"></iframe>
  </div>

  <style>
    html, body { overflow-x: hidden; }            /* nav can overflow sideways on small screens */
    #avatar-embed {
      position: fixed; left: 0;
      width: 100vw; max-width: none;              /* beat the theme's content-column max-width */
      margin: 0; padding: 0; z-index: 1;
      background: #032147;                        /* navy backdrop while the app loads */
    }
    #avatar-frame { width: 100%; height: 100%; border: 0; display: block; margin: 0; }
  </style>

  <script>
  (function () {
    var BASE = 'https://avatar.edwarddonner.com'; /* same-site as the host page -> first-party cookies */
    var box = document.getElementById('avatar-embed');
    var frame = document.getElementById('avatar-frame');

    frame.src = BASE + '/' + location.search;     /* passthrough: edwarddonner.com/avatar?q=2 */

    function fit() {
      var header = document.querySelector('header, .wp-site-blocks > header, .site-header');
      var top = header ? Math.max(0, Math.round(header.getBoundingClientRect().bottom)) : 0;
      box.style.top = top + 'px';
      box.style.height = 'calc(100dvh - ' + top + 'px)';
    }
    fit();
    addEventListener('resize', fit);
    addEventListener('orientationchange', fit);
  })();
  </script>
  ```
