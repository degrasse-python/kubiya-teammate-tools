from kubiya_sdk.tools import Arg
from tools.base import BDRTool, register_bdr_tool

get_envs = BDRTool(
    name="get_envs",
    description="Get Environment Variables",
    content="python printenv.py",
    args=[],
    mermaid_diagram="..."  # Add mermaid diagram here
)

get_github_repo_commit_list = BDRTool(
    name="get_github_repo_commit_list",
    description="Retrieve all the recent code committers from a github repo using this url",
    content="python gitusers.py --github_repo_url '$github_repo_url' ",
    args=[
        Arg(name="github_repo_url", type="str", description="Github repo endpoint", required=True),
    ],
    mermaid_diagram="..."  # Add mermaid diagram here
)

for tool in [get_envs, get_github_repo_commit_list]:
    register_bdr_tool(tool)