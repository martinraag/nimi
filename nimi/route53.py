import re
import boto3

# The following functions are for interacting with Route53, but are included in handler.py to enable
# a simplified single-file Lambda deplyment.
from nimi.handler import get_alias_record, get_record, compare_record


client = boto3.client("route53")


class SubdomainIterator(object):
    """Iterate over subdomains of a hostname to the root domain"""

    def __init__(self, hostname):
        normalised_hostname = hostname.encode("idna").decode()
        if not self._is_valid_hostname(normalised_hostname):
            raise Exception("Invalid hostname")
        self.hostname_parts = hostname.split(".")

    def __iter__(self):
        self.current = -len(self.hostname_parts)
        return self

    def __next__(self):
        if self.current > -2:
            raise StopIteration
        else:
            current = self.current
            self.current += 1
            return ".".join(self.hostname_parts[current:])

    def _is_valid_hostname(self, hostname):
        if hostname[-1] == ".":
            hostname = hostname[:-1]
        if len(hostname) > 253:
            return False
        allowed = re.compile(r"(?!-)[A-Z\d\-\_]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(part) for part in hostname.split("."))


def find_hosted_zone(hostname):
    # TODO: Support pagination for > 100 zones
    hosted_zones = client.list_hosted_zones()["HostedZones"]
    if len(hosted_zones) < 1:
        return

    subdomains = SubdomainIterator(hostname)
    for subdomain in subdomains:
        match = [
            zone for zone in hosted_zones if compare_record(zone["Name"], subdomain)
        ]
        if match:
            return match[0]


def get_ns_record(hosted_zone_id, record_name):
    return get_record(hosted_zone_id, record_name, "NS")


def wait_resource_record_sets_changed(response):
    if response["ChangeInfo"]["Status"] == "INSYNC":
        return
    waiter = client.get_waiter("resource_record_sets_changed")
    return waiter.wait(Id=response["ChangeInfo"]["Id"])


def create_hosted_zone(domain):
    """Creates new hosted zone for provided domain and returns list of name servers."""

    response = client.create_hosted_zone(
        Name=domain,
        CallerReference=f"nimi-import-{domain}",
        HostedZoneConfig={"Comment": "Hosted zone create by Nimi Dynamic DNS client."},
    )
    wait_resource_record_sets_changed(response)
    # TODO: NS records should always be created by AWS, but would be good to handle a missing record
    name_servers = get_ns_record(response["HostedZone"]["Id"], domain).values
    return name_servers


def delete_hosted_zone(domain):
    hosted_zone_id = find_hosted_zone_id(domain)
    if not hosted_zone_id:
        return
    response = client.delete_hosted_zone(Id=hosted_zone_id)
    wait_resource_record_sets_changed(response)


def find_hosted_zone_id(hostname):
    hosted_zone = find_hosted_zone(hostname)
    if hosted_zone:
        return hosted_zone["Id"].split("/")[2]


def remove_alias_record(zone_id, record_name):
    record = get_alias_record(zone_id, record_name)
    if not record:
        return

    response = client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "DELETE",
                    "ResourceRecordSet": {
                        "Name": record_name,
                        "Type": "A",
                        "TTL": record.ttl,
                        "ResourceRecords": [
                            {"Value": value} for value in record.values
                        ],
                    },
                }
            ]
        },
    )
    wait_resource_record_sets_changed(response)
