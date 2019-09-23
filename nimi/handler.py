import collections
import hashlib
import hmac
import json
import os

import boto3


CONFIG_OPTIONS = ["HOSTED_ZONE_ID", "SHARED_SECRET", "TTL"]
Record = collections.namedtuple("Record", ["type", "ttl", "values"])
route53 = boto3.client("route53")


def lambda_handler(event, context):
    try:
        request = json.loads(event["body"])
    except json.JSONDecodeError:
        return Response.bad_request(error="Invalid payload")

    if not "hostname" in request or not "signature" in request:
        return Response.bad_request(error="Invalid payload")

    config = get_configuration(request["hostname"])
    if not config:
        return Response.bad_request(error="Invalid hostname")

    signature = hmac.new(
        config["shared_secret"].encode("utf-8"),
        request["hostname"].encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, request["signature"]):
        return Response.unauthorized(error="Unauthorized")

    record = get_alias_record(config["hosted_zone_id"], request["hostname"])
    request_ip = event["requestContext"]["identity"]["sourceIp"]
    if not record or not current_ip in record.values:
        set_alias_record(
            config["hosted_zone_id"],
            request["hostname"],
            request_ip,
            int(config["ttl"]),
        )

    return Response.ok(ip=request_ip)


def get_configuration(hostname):
    """Reads configuration options from environment and returns a dict of options or None.
    Expects all options to be configured for a hostname.
    """

    env_prefix = hostname.replace(".", "_").upper()
    options = set([f"{env_prefix}__{option}" for option in CONFIG_OPTIONS])
    if not options.issubset(set(os.environ.keys())):
        return
    return {
        key.split("__")[1].lower(): value
        for key, value in os.environ.items()
        if key in options
    }


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
        return {"statusCode": statusCode, "body": json.dumps(kwargs)}


# The following functions are for interacting with Route53 and are included in handler.py to enable
# a simplified single-file Lambda deplyment.


def get_record(zone_id, record_name, record_type):
    """Query records from zone id matching name and type. Returns Record object or None."""

    record_sets = route53.list_resource_record_sets(
        HostedZoneId=zone_id, StartRecordName=record_name, StartRecordType=record_type
    )
    for record_set in record_sets["ResourceRecordSets"]:
        if (
            not compare_record(record_set["Name"], record_name)
            or record_set["Type"] != record_type
        ):
            continue
        values = [record["Value"] for record in record_set["ResourceRecords"]]
        # Return first matching record, there should only ever be one
        return Record(record_type, record_set["TTL"], values)


def get_alias_record(zone_id, record_name):
    """Query A records and return first matching Record."""

    return get_record(zone_id, record_name, "A")


def set_alias_record(zone_id, record_name, ip_address, ttl):
    """Creates new change request to upsert an A record."""

    route53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": record_name,
                        "Type": "A",
                        "TTL": ttl,
                        "ResourceRecords": [{"Value": ip_address}],
                    },
                }
            ]
        },
    )


def compare_record(record_name, hostname):
    return f"{hostname}." == record_name
