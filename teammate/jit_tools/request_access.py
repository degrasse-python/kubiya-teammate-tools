import os
import sys
from datetime import datetime, timedelta
import requests
import uuid
import json

import argparse
import redis
from redis.exceptions import ResponseError, ConnectionError
from litellm import completion
import boto3
import asyncio

USER_EMAIL = os.getenv('KUBIYA_USER_EMAIL')
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')
SLACK_THREAD_TS = os.getenv('SLACK_THREAD_TS')
KUBIYA_USER_ORG = os.getenv('KUBIYA_USER_ORG')
KUBIYA_JIT_WEBHOOK = os.getenv('KUBIYA_JIT_WEBHOOK')
JIT_API_KEY = os.getenv('JIT_API_KEY')
APPROVAL_SLACK_CHANNEL = os.getenv('APPROVAL_SLACK_CHANNEL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_API_BASE = os.getenv('OPENAI_API_BASE')
BACKEND_URL = os.getenv('BACKEND_URL')
BACKEND_PORT = os.getenv('BACKEND_PORT')
BACKEND_DB = os.getenv('BACKEND_DB')
BACKEND_PASS = os.getenv('BACKEND_PASS')
GPT_API_KEY=os.getenv('GPT_API_KEY')
GPT_ENDPOINT=os.getenv('GPT_ENDPOINT')
AWS_ACCESS_KEY_ID=os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY=os.getenv('AWS_SECRET_ACCESS_KEY')


class StripArgument(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.strip())


def generate_policy(description, demo=False):
  print("✨ Generating least privileged policy JSON...")
  if not demo:
    messages = [{"content": f"Generate a least privileged policy JSON for the following description: {description} - return the JSON object.", "role": "user"}]
    try:
      response = completion(model="gpt-4o", 
                            messages=messages,
                            api_key=GPT_API_KEY,
                            base_url=GPT_ENDPOINT
                            ) 
      if not response['choices']:
        print("❌ Error: No response from OpenAI API. Could not generate policy.")
        sys.exit(1)
      content = response['choices'][0]['message']['content']
      start = content.find('{')
      end = content.rfind('}')
      policy = content[start:end+1] if start != -1 and end != -1 else content
      return json.loads(policy)
    except Exception as e:
      print(f"❌ Policy generation failed: {e}")
      sys.exit(1)
  else:
    ec2policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                  "ec2:DescribeInstances", 
                  "ec2:DescribeImages",
                  "ec2:DescribeTags", 
                  "ec2:DescribeSnapshots"
                ],
                "Resource": "*"
                }
            ]
          }
    return json.dumps(ec2policy)
    

def validate_aws_policy(policy_document):
  """Ensure all required environment variables are set."""
  iam_client = boto3.client('iam',
                        aws_access_key_id=AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
  policy_document_json = json.dumps(policy_document)
  try:
  # Attempt simulation with an empty list of actions, which won’t simulate but will validate structure
    response = iam_client.simulate_custom_policy(
        PolicyInputList=[policy_document_json],
        ActionNames=[],
    )
    print("Policy structure is valid.")
  except Exception as e:
      print("Policy structure is invalid:", e)
      raise

def create_request_id():
  name = 'kubiya-jit-' + str(uuid.uuid4())
  return name

def time_format(ttl):
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
  return ttl_minutes

if __name__ == "__main__":

  ### ----- Parse command-line arguments ----- ###
  # Get args from Kubiya
  parser = argparse.ArgumentParser(description="Trigger a request for just in time permissions that require approval from another user.")
  parser.add_argument("--purpose", 
                      nargs='+', # action=StripArgument ,
                      required=True, 
                      help="Purpose of the request for just in time permissions.")
  parser.add_argument("--ttl", required=True, help="The time to live (ttl) for the permissions request.")
  parser.add_argument("--permission_set_name", 
                      required=True, 
                      nargs='+', # action=StripArgument ,
                      help="The permissions set name for permissions request.")
  parser.add_argument("--policy_description", 
                      required=True,
                      nargs='+', # action=StripArgument ,
                      help="The policy description for the just in time request.")
  args = parser.parse_args()

  # Parameters
  purpose = args.purpose
  ttl = args.ttl
  permission_set_name = args.permission_set_name
  policy_description = ' '.join(args.policy_description)
  policy_name = create_request_id()
  request_id = policy_name
  llm_policy = generate_policy(policy_description)
  policy_json = json.loads(llm_policy)
  validate_aws_policy(policy_json)
  ttl_minutes = time_format(ttl)
  
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
  print(f"📝 Creating approval request")

  ap_request_json =  {
                        request_id:
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
  
  print(f"✅ Generated least privileged policy ")
  print(f"✅ For Request ID:\n\n{request_id}")
  print(BACKEND_DB, BACKEND_PORT, BACKEND_URL, BACKEND_PASS)

  ### ----- Redis Client ----- ###
  rd = redis.Redis(host=BACKEND_URL, 
                  port=BACKEND_PORT, 
                  password=BACKEND_PASS,)
  # --- Store request in Redis --- #  
  ressadd = rd.sadd(request_id, json.dumps(ap_request_json))

  ### ----- LLM Setup ----- ### 
  # --- Prompt sent to new Kubiya agent thread TODO -- Add correct API endpoint or remove prompt and use webhook.
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

  ### ----- Create and send webhook ----- ###
  # payload
  print(f"📝 Sending webhook request")
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

  webhook_payload = {
    "communication": {
        "destination": APPROVAL_SLACK_CHANNEL, 
        "method": "Slack"
    },
    "created_at": datetime.utcnow().isoformat() + "Z",
    "created_by": USER_EMAIL,
    "name": "Approval Request",
    "org": KUBIYA_USER_ORG,
    'USER_EMAIL': USER_EMAIL,
    'purpose': policy_json,
    'request_id': json_id, 
    'policy_json': policy_json,
    'ttl': ttl,
    "source": "Triggered by an access request (Agent)",
    "updated_at": datetime.utcnow().isoformat() + "Z"
  }

  # --- send to API
  # response = requests.post("https://api.kubiya.ai/api/v1/event",headers={'Content-Type': 'application/json','Authorization': f'UserKey {JIT_API_KEY}'},json=payload)
  
  ### ----- Send to Webhook ----- ###
  response = requests.post(
      KUBIYA_JIT_WEBHOOK,
      headers={
          'Content-Type': 'application/json',
      },
      json=webhook_payload
  )

  if response.status_code < 300:
    print(f"✅ WAITING: Request submitted successfully and has been sent to an approver. Waiting for approval.")
  else:
    print(f"❌ Error sending webhook event: {response.status_code} - {response.text}")
    sys.exit(1)
