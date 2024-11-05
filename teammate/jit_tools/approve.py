import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
import requests
import json

import argparse
import redis
from pytimeparse.timeparse import timeparse



APPROVER_USER_EMAIL = os.getenv('KUBIYA_USER_EMAIL')
APPROVAL_SLACK_CHANNEL = os.getenv('APPROVAL_SLACK_CHANNEL')
APPROVING_USERS = os.getenv('APPROVING_USERS', '').split(',') #TODO create list of named emails that can approve this request.
SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
JIT_API_KEY = os.getenv('JIT_API_KEY')
BACKEND_URL = os.getenv('BACKEND_URL')
BACKEND_PORT = os.getenv('BACKEND_PORT')
BACKEND_DB = os.getenv('BACKEND_DB')
BACKEND_PASS = os.getenv('BACKEND_PASS')


# TODO make key available for this POV or use hardcoded json policy in meantime. 

if __name__ == "__main__":

  ### ----- Parse command-line arguments ----- ###
  # Get args from Kubiya
  parser = argparse.ArgumentParser(description="Trigger a search for github users")
  parser.add_argument("--request_id", required=True, help="The url of the git repo")
  parser.add_argument("--approval_action", required=True, help="The url of the git repo")

  args = parser.parse_args()
  request_id = args.request_id
  approval_action = args.approval_action


  ### ----- Redis Client ----- ###
  rd = redis.Redis(host=BACKEND_URL, 
                  port=BACKEND_PORT, 
                  password=BACKEND_PASS,)

  # --- get byte list
  res = rd.smembers(request_id)
  # --- decode list member of bytes into str
  load = res[0].decode('utf8').replace("'", '"')
  # --- load into json
  approval_request = json.loads(load)

  # Parse command-line arguments
  args = parser.parse_args()

  # Get coordinates for the given city
  name = args.name

  if not APPROVER_USER_EMAIL:
    print("❌ Missing APPROVER_USER_EMAIL environment variable")
    sys.exit(1)

  if approval_action not in ['approved', 'rejected']:
    print("❌ Error: Invalid approval action. Use 'approved' or 'rejected'.")
    sys.exit(1)

  if APPROVER_USER_EMAIL not in APPROVING_USERS:
    print(f"❌ User {APPROVER_USER_EMAIL} is not authorized to approve this request")
    sys.exit(1)

  if not approval_request:
    print(f"❌ No pending approval request found for request ID {request_id}")
    sys.exit(1)


  print(f"✅ Approval request with ID {request_id} has been {approval_action}")

  if approval_action == "approved":
    duration_minutes = approval_request[request_id]['ttl_min']

    # Set the future time to remove the policy based on ISO format and duration
    duration_seconds = timeparse(f"{duration_minutes}m")
    if duration_seconds is None:
      raise ValueError("Invalid duration format")

    # Convert duration_seconds to a timedelta
    duration_timedelta = timedelta(seconds=duration_seconds)

    now = datetime.now(timezone.utc)  # Get the current time in UTC with timezone
    schedule_time = now + duration_timedelta
    try:
      schedule_time = schedule_time.isoformat()
    except Exception as e:
      print(f"❌ Error: Could not place future deletion time in ISO format: {e}")
      print(f"As a fallback, the policy will be removed in 1 hour.")
      # Fallback to 1 hour
      schedule_time = now + timedelta(hours=1)
      schedule_time = schedule_time.isoformat()
    
    task_payload = {
        "scheduled_time": schedule_time,
        # TODO:: Notify both ends on Slack (easy to do with a dedicated Slack tool)
        "task_description": f"Immediately remove policy {approval_request[request_id]['policy_name']} from permission set {approval_request[request_id]['permission_set_name']} as the TTL has expired",
        "channel_id": APPROVAL_SLACK_CHANNEL,
        "user_email": approval_request[request_id]['user_email'],
        "organization_name": os.getenv("KUBIYA_USER_ORG"),
        "agent": os.getenv("KUBIYA_AGENT_PROFILE")
    }
    response = requests.post(
        'https://api.kubiya.ai/api/v1/scheduled_tasks',
        headers={
            'Authorization': f'UserKey {JIT_API_KEY}',
            'Content-Type': 'application/json'
        },
        json=task_payload
    )

    if response.status_code < 300:
      print(f"✅ Scheduled task to remove policy `{approval_request[request_id]['policy_name']}` from permission set `{approval_request[request_id]['permission_set_name']}` in `{duration_minutes} minutes` (expires at `{schedule_time}`)")
    else:
      print(f"❌ Error: {response.status_code} - {response.text}")

  slack_channel_id = approval_request[request_id]['slack_channel_id']
  slack_thread_ts = approval_request[request_id]['slack_thread_ts']

  # Get permalink
  permalink_response = requests.get(
      "https://slack.com/api/chat.getPermalink",
      params={
          'channel': slack_channel_id,
          'message_ts': slack_thread_ts
      },
      headers={
          'Authorization': f'Bearer {SLACK_API_TOKEN}'
      }
  )

  permalink = permalink_response.json().get("permalink")

  action_emoji = ":white_check_mark:" if approval_action == "approved" else ":x:"
  action_text = "APPROVED" if approval_action == "approved" else "REJECTED"
  approver_text = f"<@{APPROVER_USER_EMAIL}> *{action_text}* your access request {action_emoji}"

  slack_payload_main_thread = {
      "channel": slack_channel_id,
      "text": f"<@{approval_request[request_id]['user_email']}>, your request has been {approval_action}.",
      "blocks": [
          {
              "type": "section",
              "text": {
                  "type": "mrkdwn",
                  "text": f"*Request {approval_action}* {action_emoji}\n \
                  *Reason:* {approval_request[request_id]['purpose']}\n*Access:* {approval_request[request_id]['policy_name']} \
                    for {approval_request[request_id]['ttl_min']}\n*Status:* {approver_text}\n<{permalink} \
                    |View original conversation>\n\nYou can now try your brand new permissions! \
                    :rocket:\n\nNote: This permission will be removed automatically after {approval_request[request_id]['ttl_min']} \
                    minutes\n\nPermission policy statement JSON:\n```{approval_request[request_id]['policy_json']}```\n\n \
                  *Next steps:* If you have any questions or need further assistance, please reach out to \
                    <@{approval_request[request_id]['user_email']}>, you can now access the resources you requested with the permissions granted."
              }
          },
          {
              "type": "actions",
              "elements": [
                  {
                      "type": "button",
                      "text": {
                          "type": "plain_text",
                          "text": "↗️💬 View Thread"
                      },
                      "url": permalink
                  }
              ]
          }
      ],
  }

  slack_payload_in_thread = {
      "channel": slack_channel_id,
      "text": f"<@{approval_request[0]}>, your request has been {approval_action}.",
      "thread_ts": slack_thread_ts,
      "blocks": [
          {
              "type": "section",
              "text": {
                  "type": "mrkdwn",
                  "text": f"*Good news!* {approver_text} :tada:\n\nGo ahead and try your brand new permissions! :rocket:\n\nNote: This permission will be removed automatically after *{approval_request[2]}*\n\nPermission policy statement JSON:\n```{approval_request[5]}```"
              }
          }
      ]
  }

  for slack_payload in [slack_payload_main_thread, slack_payload_in_thread]:
    slack_response = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {SLACK_API_TOKEN}'
        },
        json=slack_payload
    )

    ### TODO --- Remove expired requests --- TODO ###
    
    
    #conn = sqlite3.connect('/sqlite_data/approval_requests.db')
    #c = conn.cursor()
    #c.execute("DELETE FROM approvals WHERE expires_at < ?", (datetime.utcnow().isoformat(),))
    #conn.commit()
    #conn.close()
    
    if slack_response.status_code < 300:
      print(f"✅ All done! Slack notification sent successfully")
    else:
      print(f"❌ Error sending Slack notification: {slack_response.status_code} - {slack_response.text}")

