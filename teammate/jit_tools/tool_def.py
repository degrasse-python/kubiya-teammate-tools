import inspect
from .base import AWSCliTool, AWSSdkTool

from kubiya_sdk.tools.models import (Tool,
                                     Arg,
                                     FileSpec)
from kubiya_sdk.tools.registry import tool_registry

from . import (request_access,
               approve)


request_access_tool = Tool(
    name="request_access",
    type="docker",
    image="python:3.12-slim",
    description="A tool to request access, generating an IAM policy based on a description and creating an approval request for admins to review",
    args=[
          Arg(name="purpose", description="reason that individual needs the policy to be granted.", required=True),
          Arg(name="ttl", description="the time to live for the policy. hours=h, minutes=m", required=True),
          Arg(name="permission_set_name", description="the name of the policy", required=True),
          Arg(name="policy_description", description="the description of the policy to be generated which includes the AWS service, actions, and Amazon Resource Name.", required=True),
          Arg(name="policy_name", description="the name of the policy", required=True),
          ],
    env=[
        "SLACK_THREAD_TS", 
        "SLACK_CHANNEL_ID",
        'BACKEND_URL',
        'BACKEND_PORT',
        'BACKEND_DB',
        'BACKEND_PASS',
        'KUBIYA_JIT_WEBHOOK',
        'APPROVAL_SLACK_CHANNEL',
        
    ],
    content="""

pip install argparse > /dev/null 2>&1
pip install redis > /dev/null 2>&1
pip install slack_sdk > /dev/null 2>&1
pip install requests > /dev/null 2>&1
pip install langchain_ollama > /dev/null 2>&1
pip install langchain_core > /dev/null 2>&1
pip install litellm==1.49.5 > /dev/null 2>&1
pip install pillow==11.0.0 > /dev/null 2>&1
pip install tempfile > /dev/null 2>&1

python /tmp/request_access.py --purpose $purpose --ttl $ttl --permission_set_name $permission_set_name --policy_description $policy_description --policy_name $policy_name
""",
    with_files=[
        FileSpec(
            destination="/tmp/request_access.py",
            content=inspect.getsource(request_access),
        ),
    ],
)

approve = Tool(
    name="approve",
    type="docker",
    image="python:3.12-slim",
    description="A tool to request access, generating an IAM policy based on a description and creating an approval request for admins to review",
    args=[
          Arg(name="request_id", description="The request id that is passed via the Kubi API to grab Redis' Json for use in the request.", required=True),
          Arg(name="approval_action", description="the decision that the approver will make for the just in time request.", required=True),
          ],
    env=[
        "SLACK_THREAD_TS", 
        "SLACK_CHANNEL_ID",
        "AWS_ACCESS_KEY",
        "AWS_SECRET_KEY",
        'BACKEND_URL',
        'BACKEND_PORT',
        'BACKEND_DB',
        'BACKEND_PASS',
        'KUBIYA_JIT_WEBHOOK',
    ],
    content="""
pip install pytimeparse > /dev/null 2>&1
pip install pytimeparse > /dev/null 2>&1
pip install boto3 > /dev/null 2>&1
pip install redis > /dev/null 2>&1
pip install slack_sdk > /dev/null 2>&1
pip install requests > /dev/null 2>&1
pip install langchain_ollama > /dev/null 2>&1
pip install langchain_core > /dev/null 2>&1
pip install litellm==1.49.5 > /dev/null 2>&1
pip install pillow==11.0.0 > /dev/null 2>&1
pip install tempfile > /dev/null 2>&1

python /tmp/approve.py --request_id $request_id --approval_action $approval_action
""",
    with_files=[
        FileSpec(
            destination="/tmp/approve.py",
            content=inspect.getsource(approve),
        ),
    ],
)

iam_list_roles = AWSCliTool(
    name="iam_list_roles",
    description="List IAM Roles",
    content="aws iam list-roles",
    args=[],
)


iam_create_policy = AWSCliTool(
    name="iam_create_policy",
    description="Create IAM Policy",
    content="aws iam create-policy \
                --policy-name $policy_name \
                --policy-document $policy_document",
    args=[Arg(name="policy_name", description="The request id that is passed via the Kubi API to grab Redis' Json for use in the request.", required=True),
          Arg(name="policy_document", description="the json used for the creation of the policy.", required=True),
          ],
)

iam_delete_policy = AWSCliTool(
    name="iam_delete_policy",
    description="Delete IAM Policy",
    content="aws iam delete-policy \
                --policy-arn $policy_arn", # format arn:aws:iam::123456789012:policy/MySamplePolicy
    args=[Arg(name="policy_arn", description="the decision that the approver will make for the just in time request.", required=True),
          ],
)


tool_registry.register("iam_list_roles", iam_list_roles)
tool_registry.register("iam_create_policy", iam_create_policy)
tool_registry.register("iam_delete_policy", iam_delete_policy)


tool_registry.register("approve", approve)
tool_registry.register("request_access", request_access_tool)
