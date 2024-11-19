from . import jit_webhook

import inspect


from kubiya_sdk.tools.models import Tool, Arg, FileSpec
from kubiya_sdk.tools.registry import tool_registry

jit_webhook_tool = Tool(
    name="jira_jit_webhook",
    type="docker",
    image="python:3.12-slim",
    description="This tool is used to receive a just-in-time policy request from Jira when a Jira issue is created.",
    args=[Arg(request="request_id", description="request_id to store request in redis.", required=True),
          Arg(purpose="purpose", description="purpose for the jit request.", required=True),
          Arg(ttl="ttl", description="ttl for the policy.", required=True),
          Arg(email="email", description="email to find the correct user to communication with in slack.", required=True),
          Arg(aws_account_id="aws_account_id", description="aws_account_id of the aws instance in.", required=False),
          Arg(jit_policyjson="jit_policyjson", description="jit_policyjson to for the infrastructure access request.", required=True)],
    content="""
curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1
. $HOME/.cargo/env

uv venv > /dev/null 2>&1
. .venv/bin/activate > /dev/null 2>&1

uv pip install -r /tmp/requirements.txt > /dev/null 2>&1

python /tmp/jit_webhook.py "{{ .request_id }}"
""",
    with_files=[
        FileSpec(
            destination="/tmp/jit_webhook.py",
            content=inspect.getsource(jit_webhook),
        ),
        FileSpec(
            destination="/tmp/requirements.txt",
            content="",  # Add any requirements here
        ),
    ],
)

tool_registry.register("hello", hello_tool)
