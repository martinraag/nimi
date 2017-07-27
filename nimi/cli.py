import os

import click
from terminaltables import SingleTable

from nimi.stack import Stack
from nimi.route53 import find_hosted_zone_id, get_alias_record, remove_alias_record
from nimi.function import Function, env_from_config


DEFAULT_STACK_NAME = 'nimi-dynamic-dns'


@click.group()
@click.option('--name', default=DEFAULT_STACK_NAME, help='AWS CloudFormation stack name.')
@click.pass_context
def cli(ctx, name):
    ctx.obj = {'stack': Stack(name)}


@cli.command()
@click.pass_context
def setup(ctx):
    """Provision AWS infrastructure."""

    stack = ctx.obj['stack']
    print('☕️  Creating CloudFormation stack')
    stack.create()


@cli.command()
@click.argument('hostname')
@click.option('--secret', help='Shared secret for updating hosts domain name alias')
@click.pass_context
def add(ctx, hostname, secret=None):
    """Add new hostname."""

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
    """Remove hostname."""

    stack = ctx.obj['stack']
    function = Function(stack.get_output('LambdaFunctionName'))
    config = function.get_config()

    if not hostname in config:
        click.echo('🤔  Hostname {} not found in configuration.'.format(hostname))
        return

    # Remove Route53 record
    click.echo('🔥  Removing DNS record')
    remove_alias_record(config[hostname]['hosted_zone_id'], hostname)

    # Remove hostname from configuration
    del config[hostname]
    env = env_from_config(config)
    hosted_zones = [host['hosted_zone_id'] for host in config.values()]
    hosted_zones = list(set(hosted_zones))

    click.echo('☕️  Updating CloudFormation stack')
    stack.update(hosted_zones=hosted_zones, env=env)


@cli.command()
@click.pass_context
def info(ctx):
    """Print configuration."""

    stack = ctx.obj['stack']
    function = Function(stack.function_name)
    config = function.get_config()

    table_data = [
        ['Hostname', 'Hosted Zone Id' ,'Current IP', 'Shared Secret']
    ]
    for hostname, options  in config.items():
        current_ip = get_alias_record(options['hosted_zone_id'], hostname)
        table_data.append([hostname, options['hosted_zone_id'], current_ip, options['shared_secret']])
    table = SingleTable(table_data, 'Hosts')
    click.echo('\n - API URL: {}\n'.format(stack.api_url))
    click.echo(table.table)


@cli.command()
@click.pass_context
def destroy(ctx):
    """Remove AWS infrastructure."""

    stack = ctx.obj['stack']
    
    # Remove Route53 records
    function = Function(stack.function_name)
    config = function.get_config()
    for hostname, options in config.items():
        click.echo('🔥  Removing DNS record for {}'.format(hostname))
        remove_alias_record(options['hosted_zone_id'], hostname)

    # Remove stack
    click.echo('🔥  Removing CloudFormation stack')
    stack.destroy()
