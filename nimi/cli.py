import os

import click

from nimi.stack import Stack
from nimi.route53 import find_hosted_zone_id
from nimi.function import Function, env_from_config


DEFAULT_STACK_NAME = 'nimi-dynamic-dns'


@click.group()
@click.option('--name', default=DEFAULT_STACK_NAME, help='AWS CloudFormation stack name')
@click.pass_context
def cli(ctx, name):
    ctx.obj = {'stack': Stack(name)}


@cli.command()
@click.pass_context
def setup(ctx):
    """Provision AWS infrastructure using CloudFormation"""

    stack = ctx.obj['stack']
    print('☕️  Creating CloudFormation stack')
    stack.create()


@cli.command()
@click.argument('hostname')
@click.option('--secret', help='Shared secret for updating hosts domain name alias')
@click.pass_context
def add(ctx, hostname, secret=None):
    """Add new domain name"""

    stack = ctx.obj['stack']
    hosted_zone_id = find_hosted_zone_id(hostname)
    secret = secret if secret else os.urandom(16).hex()

    # Update existing function environment with new values
    function = Function(stack.get_output('LambdaFunctionName'))
    config = function.get_config()
    config[hostname] = {
        'hosted_zone_id': hosted_zone_id,
        'shared_secret': secret
    }
    env = env_from_config(config)

    # Create a list of unique hosted zone id's
    hosted_zones = [host['hosted_zone_id'] for host in config.values()]
    hosted_zones.append(hosted_zone_id)
    hosted_zones = list(set(hosted_zones))

    click.echo('☕️  Updating CloudFormation stack')
    stack.update(hosted_zones=hosted_zones, env=env)


@cli.command()
@click.argument('hostname')
@click.pass_context
def remove(ctx, hostname):
    """Remove domain name"""

    stack = ctx.obj['stack']
    function = Function(stack.get_output('LambdaFunctionName'))
    config = function.get_config()

    if not hostname in config:
        click.echo('🤔  Hostname {} not found in configuration.'.format(hostname))
        return

    del config[hostname]
    env = env_from_config(config)

    hosted_zones = [host['hosted_zone_id'] for host in config.values()]
    hosted_zones = list(set(hosted_zones))

    click.echo('☕️  Updating CloudFormation stack')
    stack.update(hosted_zones=hosted_zones, env=env)


@cli.command()
@click.pass_context
def destroy(ctx):
    """Remove AWS infrastructure"""

    stack = ctx.obj['stack']
    click.echo('🔥  Removing CloudFormation stack')
    stack.destroy()


if __name__ == '__main__':
    cli()
