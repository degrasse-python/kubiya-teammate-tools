# k8s_tools/tools/base.py
from kubiya_sdk.tools import Tool
from .common import (COMMON_ENVIRONMENT_VARIABLES, 
                     COMMON_FILE_SPECS)

KUBERNETES_ICON_URL = "https://cdn-icons-png.flaticon.com/256/3889/3889548.png"
INIT_SH="""#!/bin/bash
set -eu
TOKEN_LOCATION="/tmp/kubernetes_context_token"
CERT_LOCATION="/tmp/kubernetes_context_cert"
# Inject in-cluster context using the temporary token file
if [ -f $TOKEN_LOCATION ] && [ -f $CERT_LOCATION ]; then
    KUBE_TOKEN=$(cat $TOKEN_LOCATION)
    kubectl config set-cluster in-cluster --server=https://kubernetes.default.svc \
                                          --certificate-authority=$CERT_LOCATION
    kubectl config set-credentials in-cluster --token=$KUBE_TOKEN
    kubectl config set-context in-cluster --cluster=in-cluster --user=in-cluster
    kubectl config use-context in-cluster
else
    echo "Error: Kubernetes context token or cert file not found at $TOKEN_LOCATION \
          or $CERT_LOCATION respectively."
    exit 1
fi
"""


class BDRTool(Tool):
    def __init__(self, name, description, args, image="python:3.11-bullseye", content=None):

        if content:
          # Prepare the script to inject in-cluster context and use the temporary token file
          inject_kubernetes_context = INIT_SH
          # Strip extra `#!/bin/bash` and remove leading spaces from the caller-provided content
          sanitized_content = content.strip().lstrip("#!/bin/bash").strip()
          # Combine the Kubernetes context setup and the caller's provided shell script
          full_content = f"""{inject_kubernetes_context}
          #                    {sanitized_content}"""
          # Initialize the Tool superclass with the combined content and other parameters
          super().__init__(
              name=name,
              description=description,
              icon_url=KUBERNETES_ICON_URL,
              type="docker",
              image=image,
              content=full_content,
              args=args,
              env=[], #COMMON_ENVIRONMENT_VARIABLES,
              with_files=COMMON_FILE_SPECS,
          )
        else:
           # Initialize the Tool superclass with the combined content and other parameters
          super().__init__(
              name=name,
              description=description,
              icon_url=KUBERNETES_ICON_URL,
              type="docker",
              image=image,
              args=args,
              env=[], #COMMON_ENVIRONMENT_VARIABLES,
              with_files=COMMON_FILE_SPECS,)
