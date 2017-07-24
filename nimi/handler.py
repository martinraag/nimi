import json
import os

import boto3

DOMAIN_NAME = os.environ['DOMAIN_NAME']
HOSTED_ZONE_ID = os.environ['HOSTED_ZONE_ID']

route53 = boto3.client('route53')

def lambda_handler(event, context):
    if event['httpMethod'] == 'GET':
        return reflect_address(event, context)
    elif event['httpMethod'] == 'PUT':
        return update_address(event, context)
    else:
        return {
            'statusCode': 404,
        }

def get_record(zone_id, record_name):
    record_sets = route53.list_resource_record_sets(
        HostedZoneId=zone_id,
        StartRecordName=record_name,
        StartRecordType='A',
        MaxItems='2'
    )
    print('Found record sets: {}'.format(record_sets))
    records = [record_set['ResourceRecords'] for record_set in record_sets['ResourceRecordSets'] if record_set['Name'] == record_name]
    if len(records) > 1:
        raise Exception('Multiple records found for record {}'.format(record_name))
    return records[0]['Value'] if records else None

def set_record(zone_id, record_name, ip_address):
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

def reflect_address(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({
            'address': event['requestContext']['identity']['sourceIp']
        })
    }


def update_address(event, context):
    if not DOMAIN_NAME or not HOSTED_ZONE_ID:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal Server Error'
            })
        }

    # if not event['headers']['Authorization'] or not event['headers']['Authorization'] == SHARED_SECRET:
    #     return {
    #         'statusCode': 401,
    #         'body': json.dumps({
    #             'error': 'Unauthorized'
    #         })
    #     }

    try:
        request = json.loads(event['body'])
    except Exception:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Invalid request body'
            })
        }
    
    if not request['domain'] == DOMAIN_NAME:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Invalid domain'
            })
        }

    try:
        existing_ip = get_record(HOSTED_ZONE_ID, DOMAIN_NAME)
    except Exception as err:
        print(err)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal Server Error: {}'.format(err)
            })
        }

    if not existing_ip or not existing_ip == request.address:
        set_record(HOSTED_ZONE_ID, DOMAIN_NAME, request['address'])

    return {
        'statusCode': 200,
        'body': event['body']
    }
