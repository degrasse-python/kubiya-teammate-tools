import os
import sys
import time
from datetime import datetime, timedelta
import requests
import uuid
import json

import argparse
import redis
from litellm import completion

# Environment variables
USER_EMAIL = os.getenv('KUBIYA_USER_EMAIL')
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')
SLACK_THREAD_TS = os.getenv('SLACK_THREAD_TS')
KUBIYA_USER_ORG = os.getenv('KUBIYA_USER_ORG')
JIT_API_KEY = os.getenv('JIT_API_KEY')
APPROVAL_SLACK_CHANNEL = os.getenv('APPROVAL_SLACK_CHANNEL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_API_BASE = os.getenv('OPENAI_API_BASE')
BACKEND_URL = os.getenv('BACKEND_URL')
BACKEND_PORT = os.getenv('BACKEND_PORT')
BACKEND_DB = os.getenv('BACKEND_DB')
BACKEND_PASS = os.getenv('BACKEND_PASS')



def generate_policy(description, demo=True):
  print("✨ Generating least privileged policy JSON...")
  if not demo:
    messages = [{"content": f"Generate a least privileged policy JSON for the following description: {description} - return the JSON object.", "role": "user"}]
    try:
      response = completion(model="gpt-4o", messages=messages) # TODO change the model to a hugging face model.
      if not response['choices']:
        print("❌ Error: No response from OpenAI API. Could not generate policy.")
        sys.exit(1)
      content = response['choices'][0]['message']['content']
      start = content.find('{')
      end = content.rfind('}')
      return content[start:end+1]
    except Exception as e:
      print(f"❌ Policy generation failed: {e}")
      sys.exit(1)
  else:
    ec2policy = {
            "Version": "2012-10-17",
              "Statement": [
                {
                  "Sid": "Stmt1730549037760",
                  "Action": "ec2:*",
                  "Effect": "Allow",
                  "Resource": "*"
                }
              ]
            }
    return json.dump(ec2policy)
    

if __name__ == "__main__":

  ### ----- Parse command-line arguments ----- ###
  # Get args from Kubiya
  parser = argparse.ArgumentParser(description="Trigger a request for just in time permissions that require approval from another user.")
  parser.add_argument("--purpose", required=True, help="Purpose of the request for just in time permissions.")
  parser.add_argument("--ttl", required=True, help="The time to live (ttl) for the permissions request.")
  parser.add_argument("--permission_set_name", required=True, help="The permissions set name for permissions request.")
  parser.add_argument("--policy_description", required=True, help="The policy description for the just in time request.")
  parser.add_argument("--policy_name", required=True, help="The policy name for the just in time request.")
  args = parser.parse_args()

  # Parameters
  purpose = args.purpose
  ttl = args.ttl
  permission_set_name = args.permission_set_name
  policy_description = args.policy_description
  policy_name = args.policy_name

  policy_json = generate_policy(policy_description)
  print(f"✅ Generated least privileged policy JSON:\n\n{policy_json}")

  try:
    if ttl[-1] == 'm':
      ttl_minutes = int(ttl[:-1])
    elif ttl[-1] == 'h':
      ttl_minutes = int(ttl[:-1]) * 60
    elif ttl[-1] == 'd':
      ttl_minutes = int(ttl[:-1]) * 60 * 24
    else:
      raise ValueError("Unsupported TTL format")
  except ValueError as e:
    print(f"❌ Error: {e}. Defaulting to 30 days.")
    ttl_minutes = 30 * 24 * 60

  request_id = str(uuid.uuid4())

  approval_request = {
      'user_email': USER_EMAIL,
      'purpose': purpose,
      'ttl_minutes': ttl_minutes,
      'policy_name': policy_name,
      'permission_set_name': permission_set_name,
      'policy_json': policy_json,
      'requested_at': datetime.utcnow().isoformat(),
      'expires_at': (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat(),
      'slack_channel_id': SLACK_CHANNEL_ID,
      'slack_thread_ts': SLACK_THREAD_TS,
      'approved': 'pending',
      'request_id': request_id
  }

  # unique_jit_id
  json_id = USER_EMAIL+ \
            request_id+':'+ \
            approval_request['requested_at']

  print(f"📝 Creating approval request")

  ap_request_json =  {
                        json_id:
                        {
                        'status': 'pending',
                        'ttl_min': approval_request['ttl_minutes'],
                        'policy_name': approval_request['policy_name'],
                        'permission_set_name': approval_request['permission_set_name'],
                        'policy_json': approval_request['policy_json'],
                        'requested_at': approval_request['requested_at'],
                        'expires_at': approval_request['expires_at'],
                        'user_email': approval_request['user_email'],
                        'slack_channel_id': approval_request['slack_channel_id'],
                        'slack_thread_ts': approval_request['slack_thread_ts'],
                        'purpose': approval_request['purpose'],
                        }
                      }
                    


  ### ----- Redis Client ----- ###
  rd = redis.Redis(host=BACKEND_URL, 
                  port=BACKEND_PORT, 
                  db=BACKEND_DB,
                  password=BACKEND_PASS,)
  ressadd = rd.sadd(json_id, str(ap_request_json))

  ### ----- LLM Setup ----- ### 
  # --- Prompt sent to new Kubiya agent thread
  prompt = """You are an access management assistant. You are currently conversing with an approving group.
              Your task is to help the approving group decide whether to approve the following access request.
              You have a new access request from {USER_EMAIL} for the following purpose: {purpose}. The user requested this access for {ttl} minutes.
              This means that the access will be revoked after {ttl} minutes in case the request is approved.
              The ID of the request is {request_id}. The policy to be created is: ```{policy_json}```\n\n
              CAREFULLY ASK IF YOU CAN MOVE FORWARD WITH THIS REQUEST. DO NOT EXECUTE THE REQUEST UNTIL YOU HAVE RECEIVED APPROVAL FROM THE USER YOU ARE ASSISTING.""".format(
      USER_EMAIL=USER_EMAIL,
      purpose=purpose,
      ttl=ttl,
      request_id=request_id,
      policy_json=policy_json
  )

  # --- Create and send webhook
  # payload
  payload = {
      "agent_id": os.getenv('KUBIYA_AGENT_UUID'),
      "communication": {
          "destination": APPROVAL_SLACK_CHANNEL, # 
          "method": "Slack"
      },
      "created_at": datetime.utcnow().isoformat() + "Z",
      "created_by": USER_EMAIL,
      "name": "Approval Request",
      "org": KUBIYA_USER_ORG,
      "prompt": prompt,
      "source": "Triggered by an access request (Agent)",
      "updated_at": datetime.utcnow().isoformat() + "Z"
  }
  # --- send to webhook
  response = requests.post(
      "https://api.kubiya.ai/api/v1/event",
      headers={
          'Content-Type': 'application/json',
          'Authorization': f'UserKey {JIT_API_KEY}'
      },
      json=payload
  )

  if response.status_code < 300:
    print(f"✅ WAITING: Request submitted successfully and has been sent to an approver. Waiting for approval.")
    event_response = response.json()
    webhook_url = event_response.get("webhook_url")
    if webhook_url:
      webhook_response = requests.post(
          webhook_url,
          headers={'Content-Type': 'application/json'},
          json=payload
      )
      if webhook_response.status_code < 300:
        print("✅ Webhook event sent successfully.")
      else:
        print(f"❌ Error sending webhook event: {webhook_response.status_code} - {webhook_response.text}")
    else:
      print("❌ Error: No webhook URL returned in the response. Could not send webhook to approving channel.")
  else:
    print(f"❌ Error: {response.status_code} - {response.text}")


