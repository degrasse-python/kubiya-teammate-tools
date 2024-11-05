import os
import sys
from datetime import datetime, timedelta, timezone
import requests
import json

import argparse
import redis
from pytimeparse.timeparse import timeparse
import boto3


APPROVER_USER_EMAIL = os.getenv('KUBIYA_USER_EMAIL')
APPROVAL_SLACK_CHANNEL = os.getenv('APPROVAL_SLACK_CHANNEL')
REQUEST_SLACK_CHANNEL = '#jit_requests'
APPROVING_USERS = ['adsaunde1@gmail.com'] #  #TODO create list of named emails that can approve this request.
SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
JIT_API_KEY = os.getenv('JIT_API_KEY')
BACKEND_URL = os.getenv('BACKEND_URL')
BACKEND_PORT = os.getenv('BACKEND_PORT')
BACKEND_DB = os.getenv('BACKEND_DB')
BACKEND_PASS = os.getenv('BACKEND_PASS')
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
KUBI_UUID = os.getenv('KUBI_UUID')

# TODO make key available for this POV or use hardcoded json policy in meantime. 

if __name__ == "__main__":

  ### ----- Parse command-line arguments ----- ###
  # Get args from Kubiya
  print(AWS_SECRET_KEY)
  print(AWS_ACCESS_KEY)
  parser = argparse.ArgumentParser(description="Just in time request filing.")
  parser.add_argument("--request_id", required=True, help="Take the request_id from the webhook sent and use that as the parameter for the request.")
  parser.add_argument("--approval_action", required=True, help="The user will anwser the request with: 'approve request' or 'deny request'")

  args = parser.parse_args()
  request_id = args.request_id
  approval_action = args.approval_action
  
  # print(f"users_test: {users_test}")
  # print(f"APPROVING_USERS: {APPROVING_USERS}")
  ### ----- Redis Client ----- ###
  rd = redis.Redis(host=BACKEND_URL, 
                  port=BACKEND_PORT, 
                  password=BACKEND_PASS,)

  # --- get byte list
  try:
    print(f"Request ID: {request_id}")
    res = rd.smembers(str(request_id))
    # --- decode list member of bytes into str
    decoded_load = [item.decode('utf-8').replace("'", '"') for item in res]

    print(decoded_load)
    load = decoded_load[0] #.decode('utf8').replace("'", '"')
    # --- load into json
    approval_request = json.loads(load)
    print(f"APPROVING_USERS: {approval_request}")
  except Exception as e:
    print(e)
    sys.exit(1)

  if not APPROVER_USER_EMAIL:
    print("❌ Missing APPROVER_USER_EMAIL environment variable")
    sys.exit(1)

  if approval_action not in ['approve', 'approved', 'rejected', 'denied']:
    print("❌ Error: Invalid approval action. Use 'approved' or 'rejected'.")
    sys.exit(1)

  if APPROVER_USER_EMAIL not in APPROVING_USERS:
    print(f"❌ User {APPROVER_USER_EMAIL} is not authorized to approve this request")
    sys.exit(1)

  if not approval_request:
    print(f"❌ No pending approval request found for request ID {request_id}")
    sys.exit(1)

  print(f"✅ Approval request with ID {request_id} has been {approval_action}")



  if approval_action in ['approve', 'approved', 'rejected', 'denied']:
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
    print("Creating Policy: ")

    ### ----- BOTO3 ----- ###
    session = boto3.Session(aws_access_key_id=AWS_ACCESS_KEY,
                            aws_secret_access_key=AWS_SECRET_KEY,
                            )
    iam_client = session.client('iam')
    try:
      response = iam_client.create_policy(
          PolicyName=approval_request[request_id]['policy_name'],
          PolicyDocument=json.dumps(approval_request[request_id]['policy_json'])
      )
      print(f"Boto3 response: {response}")

      print(f"Policy created successfully: {response['Policy']['Arn']}")
    except iam_client.exceptions.EntityAlreadyExistsException:
        print(f"Policy {approval_request[request_id]['policy_name']} already exists.")
        sys.exit(1)
    except Exception as e:
        print(f"Error creating policy: {e}")
        sys.exit(1)

    ### TODO --- Remove expired requests --- TODO ###
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
    sch_task ={
                  'cron_string': "",
                  'schedule_time': schedule_time, # time in iso format
                  'channel_id': APPROVAL_SLACK_CHANNEL,
                  'task_description': f"Delete iam role with arn {response['Policy']['Arn']}", # TODO replace name with ARN
                  'selected_agent': KUBI_UUID
              }
    

    response = requests.post(
        'https://api.kubiya.ai/api/v1/scheduled_tasks', # TODO change to the correct endpoint
        headers={
            'Authorization': f'UserKey {JIT_API_KEY}',
            'Content-Type': 'application/json'
        },
        json=sch_task
    )
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
  }



  slack_payload_in_thread = {
      "channel": slack_channel_id,
      "text": f"<@{approval_request[request_id]['user_email']}>, your request has been {approval_action}.",
      "thread_ts": approval_request[request_id]['slack_thread_ts'],

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
  
    if slack_response.status_code < 300:
      print(f"✅ All done! Slack notification sent successfully")
    else:
      print(f"❌ Error sending Slack notification: {slack_response.status_code} - {slack_response.text}")

