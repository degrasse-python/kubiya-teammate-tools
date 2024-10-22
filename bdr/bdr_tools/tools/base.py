from kubiya_sdk.tools import Tool

from tools.common import (COMMON_ENVIRONMENT_VARIABLES, 
                          COMMON_FILE_SPECS)


ICON_URL = "https://cloud.google.com/_static/cloud/images/social-icon-google-cloud-1200-630.png"

class BDRTool(Tool):
    def __init__(self, name, description, content, args, long_running=False, mermaid_diagram=None):
        super().__init__(
            name=name,
            description=description,
            icon_url=ICON_URL,
            type="docker",
            image="python:3.11-bullseye",
            content=content,
            args=args,
            env=["GITHUB_TOKEN"],
            with_files=COMMON_FILE_SPECS,
            long_running=long_running,
            mermaid=mermaid_diagram
        )

def register_bdr_tool(tool):
    from kubiya_sdk.tools.registry import tool_registry
    tool_registry.register("bdr", tool)