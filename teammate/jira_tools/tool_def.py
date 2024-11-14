from . import jit_webhook

import inspect


from kubiya_sdk.tools.models import Tool, Arg, FileSpec
from kubiya_sdk.tools.registry import tool_registry

jit_webhook_tool = Tool(
    name="say_hello",
    type="docker",
    image="python:3.12-slim",
    description="This tool is used to receive a just-in-time policy request from Jira when a Jira issue is created.",
    args=[Arg(name="name", description="name to say hello to", required=True)],
    content="""
curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1
. $HOME/.cargo/env

uv venv > /dev/null 2>&1
. .venv/bin/activate > /dev/null 2>&1

uv pip install -r /tmp/requirements.txt > /dev/null 2>&1

python /tmp/main.py "{{ .name }}"
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
