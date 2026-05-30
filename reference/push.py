import os
import requests
from agents import function_tool
from dotenv import load_dotenv

load_dotenv(override=True)


pushover_url = "https://api.pushover.net/1/messages.json"
pushover_user = os.getenv("PUSHOVER_USER")
pushover_token = os.getenv("PUSHOVER_TOKEN")

def push(message: str) -> str:
    payload = {"user": pushover_user, "token": pushover_token, "message": message}
    result = requests.post(pushover_url, data=payload).status_code
    return f"Message pushed with status code {result}."

@function_tool
def push_tool(message: str) -> str:
    """
    Send the given messsage to the human operator (your human twin) as a Push Notification

    Args:
        message: The message to send to the human operator
    """
    return push(message)
