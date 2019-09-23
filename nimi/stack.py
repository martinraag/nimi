import os

import boto3
from botocore.exceptions import ClientError
import jinja2


TEMPLATE_FILE = "template.yml"
FUNCTION_FILE = "handler.py"


class StackNotFound(Exception):
    pass


class DuplicateStack(Exception):
    pass


class Stack(object):
    def __init__(self, name):
        self._name = name
        self._client = boto3.client("cloudformation")
        self._stack = None

    @property
    def api_url(self):
        return self._get_output("ApiUrl")

    @property
    def function_name(self):
        return self._get_output("LambdaFunctionName")

    def exists(self):
        return self._get_stack() != None

    def create(self):
        if self.exists():
            raise DuplicateStack(f"Stack {self._name} already exists. Cannot create.")
        params = self._create_stack_parameters()
        self._client.create_stack(**params)
        waiter = self._client.get_waiter("stack_create_complete")
        waiter.wait(StackName=self._name)

    def update(self, **kwargs):
        if not self.exists():
            raise StackNotFound(f"Stack {self._name} does not exist. Cannot update.")
        params = self._create_stack_parameters(**kwargs)
        self._client.update_stack(**params)
        waiter = self._client.get_waiter("stack_update_complete")
        waiter.wait(StackName=self._name)

    def destroy(self):
        if not self.exists():
            return
        self._client.delete_stack(StackName=self._name)
        waiter = self._client.get_waiter("stack_delete_complete")
        waiter.wait(StackName=self._name)

    def _get_output(self, key):
        if not self.exists():
            raise StackNotFound(
                f"Stack {self._name} does not exist. Cannot read outputs."
            )
        for output in self._get_stack()["Outputs"]:
            if output["OutputKey"] == key:
                return output["OutputValue"]

    def _get_stack(self):
        if not self._stack:
            # TODO: Support paginated results
            # XXX: boto3 throws if stack with provided name does not exist, would be nicer to do
            #      list_stacks here instead of the hacky try-except block
            try:
                response = self._client.describe_stacks(StackName=self._name)
            except ClientError as err:
                if err.response["Error"]["Code"] == "ValidationError":
                    return
                raise err

            if not response["Stacks"]:
                return
            self._stack = response["Stacks"][0]
        return self._stack

    def _create_stack_parameters(self, **kwargs):
        return {
            "StackName": self._name,
            "TemplateBody": self._get_template(**kwargs),
            "Parameters": [
                {
                    "ParameterKey": "LambdaFunctionCode",
                    "ParameterValue": self._get_function(),
                }
            ],
            "Capabilities": ["CAPABILITY_IAM"],
        }

    def _get_function(self):
        return self._read_file(FUNCTION_FILE)

    def _get_template(self, **kwargs):
        template = jinja2.Template(self._read_file(TEMPLATE_FILE))
        return template.render(**kwargs)

    def _read_file(self, filename):
        with open(os.path.join(os.path.dirname(__file__), filename), "r") as file_obj:
            return "".join(file_obj.readlines())
