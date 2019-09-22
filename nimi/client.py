import hashlib
import hmac
import json

import click
import requests


@click.group()
def cli():
    pass


@cli.command()
@click.argument("url")
@click.argument("hostname")
@click.argument("secret")
@click.option("--rate", default=5, help="Ping rate in minutes")
def setup(url, hostname, secret, rate):
    """Setup automatic execution of ping command"""

    pass


@cli.command()
@click.argument("url", envvar="NIMI_ENDPOINT_URL")
@click.argument("hostname", envvar="NIMI_HOSTNAME")
@click.argument("secret", envvar="NIMI_SECRET")
def ping(url, hostname, secret):
    """Call the Lambda function to update the IP of the hostname"""

    signature = hmac.new(
        secret.encode("utf-8"), hostname.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    payload = {"hostname": hostname, "signature": signature}
    requests.put(url, json.dumps(payload))


if __name__ == "__main__":
    cli()
