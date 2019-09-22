import boto3


def config_from_env(env):
    hosts = {}
    for key, value in env["Variables"].items():
        parts = key.split("__")
        hostname = parts[0].replace("_", ".").lower()
        key = parts[1].lower()
        if hostname in hosts:
            hosts[hostname].update({key: value})
        else:
            hosts[hostname] = {key: value}
    return hosts


def env_from_config(hosts):
    env = {}
    for host, options in hosts.items():
        key_prefix = host.replace(".", "_").upper()
        for key, value in options.items():
            env[f"{key_prefix}__{key.upper()}"] = value
    return env


class Function(object):
    def __init__(self, name):
        self._name = name
        self._client = boto3.client("lambda")

    def get_config(self):
        config = self._client.get_function_configuration(FunctionName=self._name)
        if not "Environment" in config.keys():
            return {}
        return config_from_env(config["Environment"])
