import hashlib
import hmac
import json
import os

import boto3


CONFIG_OPTIONS = ['HOSTED_ZONE_ID', 'SHARED_SECRET']
route53 = boto3.client('route53')


def lambda_handler(event, context):
    try:
        request = json.loads(event['body'])
    except json.JSONDecodeError:
        return Response.bad_request(error='Invalid payload')

    if not 'hostname' in request or not 'signature' in request:
        return Response.bad_request(error='Invalid payload')

    config = get_configuration(request['hostname'])
    if not config:
        return Response.bad_request(error='Invalid hostname')

    signature = hmac.new(
        config['shared_secret'].encode('utf-8'),
        request['hostname'].encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, request['signature']):
        return Response.unauthorized(error='Unauthorized')

    current_ip = get_alias_record(config['hosted_zone_id'], request['hostname'])
    request_ip = event['requestContext']['identity']['sourceIp']
    if not current_ip or not current_ip == request_ip:
        set_alias_record(config['hosted_zone_id'], request['hostname'], request_ip)

    return Response.ok(ip=request_ip)


def get_configuration(hostname):
    env_prefix = hostname.replace('.', '_').upper()
    options = set(['{}__{}'.format(env_prefix, option) for option in CONFIG_OPTIONS])
    if not options.issubset(set(os.environ.keys())):
        return
    return {key.split('__')[1].lower(): value for key, value in os.environ.items() if key in options}


def get_record(zone_id, record_name, record_type):
    record_sets = route53.list_resource_record_sets(
        HostedZoneId=zone_id,
        StartRecordName=record_name,
        StartRecordType=record_type
    )
    # Filter all ResourceRecords's that ResourceRecordSets' Name and Type match
    records = [
        record_set['ResourceRecords'] for record_set in record_sets['ResourceRecordSets']
        if compare_record(record_set['Name'], record_name) and record_set['Type'] == record_type
    ]
    # Extract all values from mathced ResourceRecords
    values = [record['Value'] for _ in records for record in _]
    return values


def get_alias_record(zone_id, record_name):
    record = get_record(zone_id, record_name, 'A')
    if record:
        return record[0]


def set_alias_record(zone_id, record_name, ip_address):
    route53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': record_name,
                        'Type': 'A',
                        'TTL': 900,
                        'ResourceRecords': [
                            {
                                'Value': ip_address
                            }
                        ]
                    }
                }
            ]
        }
    )


def compare_record(record_name, hostname):
    return '{}.'.format(hostname) == record_name


class Response(object):
    """Helper class to create Lambda proxy response"""

    @classmethod
    def ok(cls, **kwargs):
        return cls.create(200, **kwargs)

    @classmethod
    def bad_request(cls, **kwargs):
        return cls.create(400, **kwargs)

    @classmethod
    def unauthorized(cls, **kwargs):
        return cls.create(401, **kwargs)

    @classmethod
    def create(cls, statusCode, **kwargs):
        return {
            'statusCode': statusCode,
            'body': json.dumps(kwargs)
        }
