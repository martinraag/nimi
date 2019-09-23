import os

import click
from terminaltables import SingleTable

from nimi.stack import Stack, StackNotFound
from nimi.route53 import (
    create_hosted_zone,
    delete_hosted_zone,
    find_hosted_zone_id,
    get_alias_record,
    get_ns_record,
    remove_alias_record,
)
from nimi.function import Function, env_from_config
from nimi.client import client


DEFAULT_STACK_NAME = "nimi-dynamic-dns"
DEFAULT_TTL = 900


@click.group()
@click.option(
    "--name", default=DEFAULT_STACK_NAME, help="AWS CloudFormation stack name."
)
@click.pass_context
def cli(ctx, name):
    ctx.obj = {"stack": Stack(name)}


cli.add_command(client)


@cli.command()
@click.pass_context
def setup(ctx):
    """Provision AWS infrastructure."""

    stack = ctx.obj["stack"]
    if stack.exists():
        click.echo("🙄  Cloudformation stack already exists")
        return
    click.echo("☕️  Creating CloudFormation stack")
    stack.create()


@cli.command(name="import")
@click.argument("domain")
@click.pass_context
def import_domain(ctx, domain):
    """Create new hosted zone for domain and return configured name servers."""

    hosted_zone_id = find_hosted_zone_id(domain)
    if hosted_zone_id:
        click.echo(f"🙄  Hosted zone already exists for domain {domain}")
        name_servers = get_ns_record(hosted_zone_id, domain).values
    else:
        click.echo(f"☕️  Creating Route53 hosted zone for domain {domain}")
        name_servers = create_hosted_zone(domain)
    table_data = [
        ["Domain", "Hosted Zone Id", "Name servers"],
        [domain, hosted_zone_id, "\n".join(name_servers)],
    ]
    table = SingleTable(table_data, "Domain")
    click.echo(table.table)


@cli.command()
@click.argument("domain")
@click.pass_context
def eject(ctx, domain):
    """Delete all A records and hosted hosted zone for domain, remove associated dynamic DNS host
    names from configuration."""

    stack, config = get_stack(ctx)

    # Find all hosts configured with domain
    hosts = [host for host in config if domain == ".".join(host.split(".")[-2:])]
    if hosts:
        click.confirm(
            f'😟  Remove dynamic DNS hosts and records: { "".join(hosts) }?', abort=True
        )
        for hostname in hosts:
            click.echo(f"🔥  Removing alias record for {hostname}")
            remove_alias_record(config[hostname]["hosted_zone_id"], hostname)
            del config[hostname]
        # Update stack with removed hosts
        click.echo("☕️  Updating CloudFormation stack")
        stack.update(**stack_options(config))

    click.confirm(f"😟  Delete hosted zone for domain {domain}?", abort=True)
    click.echo(f"🔥  Removing Route53 hosted zone for {domain}")
    delete_hosted_zone(domain)


@cli.command()
@click.argument("hostname")
@click.option("--ttl", default=DEFAULT_TTL, help="TTL to set for DNS A record")
@click.option("--secret", help="Shared secret for updating hosts domain name alias")
@click.pass_context
def add(ctx, hostname, ttl, secret=None):
    """Add new hostname."""

    stack, config = get_stack(ctx)
    hosted_zone_id = find_hosted_zone_id(hostname)
    if not hosted_zone_id:
        click.echo(f"🤔  No hosted zone found for domain {hostname}")
        return
    secret = secret if secret else os.urandom(16).hex()

    # Update existing function environment with new values
    config[hostname] = {
        "hosted_zone_id": hosted_zone_id,
        "shared_secret": secret,
        "ttl": ttl,
    }
    click.echo("☕️  Updating CloudFormation stack")
    stack.update(**stack_options(config))


@cli.command()
@click.argument("hostname")
@click.pass_context
def remove(ctx, hostname):
    """Remove hostname."""

    stack, config = get_stack(ctx)

    if not hostname in config:
        click.echo(f"🤔  Hostname {hostname} not found in configuration.")
        return

    # Remove alias record
    click.confirm(f"😟  Remove DNS record for {hostname}?", abort=True)
    click.echo("🔥  Removing DNS record")
    remove_alias_record(config[hostname]["hosted_zone_id"], hostname)

    # Remove hostname from configuration
    del config[hostname]
    click.echo("☕️  Updating CloudFormation stack")
    stack.update(**stack_options(config))


@cli.command()
@click.pass_context
def info(ctx):
    """Print configuration."""

    stack, config = get_stack(ctx)
    table_data = [["Hostname", "Hosted Zone Id", "Current IP", "TTL", "Shared Secret"]]
    for hostname, options in config.items():
        record = get_alias_record(options["hosted_zone_id"], hostname)
        current_ip = "\n".join(record.values) if record else ""
        ttl = record.ttl if record else options["ttl"]
        table_data.append(
            [
                hostname,
                options["hosted_zone_id"],
                current_ip,
                ttl,
                options["shared_secret"],
            ]
        )
    table = SingleTable(table_data, "Hosts")
    click.echo(f"\n - API URL: {stack.api_url}\n")
    click.echo(table.table)


@cli.command()
@click.pass_context
def destroy(ctx):
    """Remove AWS infrastructure."""

    stack, config = get_stack(ctx)
    click.confirm(
        "😟  Delete all configured records and CloudFormation stack?", abort=True
    )
    for hostname, options in config.items():
        click.echo(f"🔥  Removing DNS record for {hostname}")
        remove_alias_record(options["hosted_zone_id"], hostname)

    # Remove stack
    click.echo("🔥  Removing CloudFormation stack")
    stack.destroy()


def get_stack(ctx):
    stack = ctx.obj["stack"]
    if not stack.exists():
        click.echo(
            (
                "🙄  CloudFormation stack not found. "
                "Create a stack first via the 'nimi setup' command."
            )
        )
        ctx.abort()
    function = Function(stack.function_name)
    config = function.get_config()
    return stack, config


def stack_options(config):
    env = env_from_config(config)
    hosted_zones = [host["hosted_zone_id"] for host in config.values()]
    hosted_zones = list(set(hosted_zones))
    return {"hosted_zones": hosted_zones, "env": env}


if __name__ == "__main__":
    cli()
