# /tools/common.py
import inspect
from kubiya_sdk.tools import FileSpec

from tools import printenv

# Common environment variables for bdr toolset
COMMON_ENVIRONMENT_VARIABLES = [
    "SLACK_CHANNEL_ID",
    "GITHUB_TOKEN",
]

# Common file specifications, including the Kubernetes service account token
COMMON_FILE_SPECS = [
    FileSpec(destination="/tmp/printenv.py", source=teammate/requirements.txtprintenv),

]