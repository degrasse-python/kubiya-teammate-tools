import os
import sys
from datetime import datetime, timedelta, timezone
import requests
import json
import argparse
import redis
from pytimeparse.timeparse import timeparse
import boto3

# Constants and configuration
APPROVER_USER_EMAIL = os.getenv('KUBIYA_USER_EMAIL')
APPROVAL_SLACK_CHANNEL = os.getenv('APPROVAL_SLACK_CHANNEL', 'C07R1TGSDPF')  # Default channel ID if not set
REQUEST_SLACK_CHANNEL = '#jit_requests'
APPROVING_USERS = ['adsaunde1@gmail.com']  # TODO: Replace with actual approver emails
SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
JIT_API_KEY = os.getenv('JIT_API_KEY')
BACKEND_URL = os.getenv('BACKEND_URL')
BACKEND_PORT = os.getenv('BACKEND_PORT')
BACKEND_DB = os.getenv('BACKEND_DB')
BACKEND_PASS = os.getenv('BACKEND_PASS')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
KUBI_UUID = os.getenv('KUBI_UUID', '760b34a8-bc05-4224-9137-bffc43bef24c')  # Default UUID if not set

def send_slack_message(channel_id, message, slack_token):
    """Send a message to a Slack channel."""
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {slack_token}"
    }
    data = {
        "channel": channel_id,
        "text": message
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200 and response.json().get("ok"):
        print("✅ Slack notification sent successfully")
    else:
        print(f"❌ Error sending Slack notification: {response.status_code} - {response.text}")
        sys.exit(1)

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Just-in-time request processing.")
    parser.add_argument("--request_id", required=True, help="The request ID from the webhook.")
    parser.add_argument("--approval_action", required=True, help="Approval action: 'approve' or 'deny'.")
    args = parser.parse_args()
    return args.request_id, args.approval_action.lower()

def validate_environment_variables():
    """Ensure all required environment variables are set."""
    required_vars = [
        'SLACK_API_TOKEN', 'JIT_API_KEY', 'BACKEND_URL',
        'BACKEND_PORT', 'BACKEND_PASS', 'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 'APPROVER_USER_EMAIL'
    ]
    missing_vars = [var for var in required_vars if not globals().get(var)]
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

def validate_aws_policy(policy_document):
  """Ensure all required environment variables are set."""
  iam_client = boto3.client('iam')
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
      

def create_redis_client():
    """Create a Redis client."""
    return redis.Redis(
        host=BACKEND_URL,
        port=BACKEND_PORT,
        password=BACKEND_PASS,
    )

def retrieve_approval_request(rd, request_id):
    """Retrieve the approval request from Redis."""
    try:
        res = rd.smembers(str(request_id))
        decoded_load = [item.decode('utf-8').replace("'", '"') for item in res]
        load = decoded_load[0]
        approval_request = json.loads(load)
        return approval_request
    except Exception as e:
        print(f"❌ Error retrieving approval request: {e}")
        sys.exit(1)

def validate_inputs_and_permissions(approval_action, approval_request, request_id):
    """Validate user permissions and request data."""
    if approval_action not in ['approve', 'approved', 'rejected', 'deny', 'denied']:
        print("❌ Invalid approval action. Use 'approve' or 'deny'.")
        sys.exit(1)
    if APPROVER_USER_EMAIL not in APPROVING_USERS:
        print(f"❌ User {APPROVER_USER_EMAIL} is not authorized to approve this request.")
        sys.exit(1)
    if not approval_request:
        print(f"❌ No pending approval request found for request ID {request_id}.")
        sys.exit(1)
    print(f"✅ Approval request with ID {request_id} has been {approval_action}.")

def create_iam_policy(approval_request, request_id):
    """Create an IAM policy using Boto3."""
    validate_aws_policy(approval_request[request_id]['policy_json'])

    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    iam_client = session.client('iam')
    try:
        response = iam_client.create_policy(
            PolicyName=approval_request[request_id]['policy_name'],
            PolicyDocument=approval_request[request_id]['policy_json']
        )
        policy_arn = response['Policy']['Arn']
        print(f"✅ Policy created successfully: {policy_arn}")
        return policy_arn
    except iam_client.exceptions.EntityAlreadyExistsException:
        print(f"❌ Policy {approval_request[request_id]['policy_name']} already exists.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error creating policy: {e}")
        sys.exit(1)

def schedule_policy_deletion(approval_request, request_id, policy_arn):
    """Schedule the policy for deletion after a specified duration."""
    try:
        now = datetime.now(timezone.utc)
        duration_minutes = approval_request[request_id]['ttl_min']
        duration_seconds = timeparse(f"{duration_minutes}m")
        if duration_seconds is None:
            raise ValueError("Invalid duration format")
        schedule_time_iso = (now + timedelta(seconds=duration_seconds)).isoformat()
    except Exception as e:
        print(f"❌ Error calculating policy expiration time: {e}")
        print("Fallback: Policy will be removed in 1 hour.")
        schedule_time_iso = (now + timedelta(hours=1)).isoformat()
    sch_task = {
        'cron_string': "",
        'schedule_time': schedule_time_iso,
        'channel_id': APPROVAL_SLACK_CHANNEL,
        'task_description': f"Delete IAM policy with ARN {policy_arn}",
        'selected_agent': KUBI_UUID
    }
    print(f"Scheduling task: {sch_task}")
    try:
        response = requests.post(
            'https://api.kubiya.ai/api/v1/scheduled_tasks',
            headers={
                'Authorization': f'UserKey {JIT_API_KEY}',
                'Content-Type': 'application/json'
            },
            json=sch_task
        )
        if response.status_code != 200:
            print(f"❌ Error scheduling task: {response.status_code} - {response.text}")
            sys.exit(1)
        print("✅ Task scheduled successfully")
    except Exception as e:
        print(f"❌ Exception while scheduling task: {e}")
        sys.exit(1)

def main():
    """Main function to process the approval request."""
    # Parse command-line arguments
    request_id, approval_action = parse_arguments()

    # Validate environment variables
    validate_environment_variables()

    # Create Redis client and retrieve approval request
    rd = create_redis_client()
    approval_request = retrieve_approval_request(rd, request_id)

    # Validate inputs and permissions
    validate_inputs_and_permissions(approval_action, approval_request, request_id)
    
    # Process approval action
    if approval_action in ['approve', 'approved']:
        policy_arn = create_iam_policy(approval_request, request_id)
        schedule_policy_deletion(approval_request, request_id, policy_arn)
    
    # Send Slack notification
    slack_channel_id = approval_request[request_id]['slack_channel_id']
    user_email = approval_request[request_id]['user_email']
    message = f"<@{user_email}>, your request has been {approval_action}. \n \
                Policy ARN: {policy_arn} \n \
                Here is the policy requested: \n \
                {approval_request} \n\n\n"
    send_slack_message(slack_channel_id, message, SLACK_API_TOKEN)

if __name__ == "__main__":
    main()