from kubiya_sdk.tools import Arg
from .base import AWSCliTool, AWSSdkTool
from kubiya_sdk.tools.registry import tool_registry


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
          Arg(name="policy_document", description="the decision that the approver will make for the just in time request.", required=True),
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
