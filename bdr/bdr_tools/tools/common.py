# /tools/common.py
import inspect
from kubiya_sdk.tools import FileSpec

from . import printenv

# Common environment variables for bdr toolset
COMMON_ENVIRONMENT_VARIABLES = [
    "SLACK_CHANNEL_ID",
]

# Common file specifications, including the Kubernetes service account token
COMMON_FILE_SPECS = [
    FileSpec(
        # Copy the service account token to a temporary location for use in the container
        source="/var/run/secrets/kubernetes.io/serviceaccount/token",
        destination="/tmp/kubernetes.k",
    ),
    FileSpec(destination="/tmp/printenv.py", source=inspect.getsource(printenv)),

]