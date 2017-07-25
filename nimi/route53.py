import re
import boto3


client = boto3.client('route53')


class SubdomainIterator(object):
    """Iterate over subdomains of a hostname to the root domain"""

    def __init__(self, hostname):
        normalised_hostname = hostname.encode("idna").decode()
        if not self._is_valid_hostname(normalised_hostname):
            raise Exception('Invalid hostname')
        self.hostname_parts = hostname.split('.')

    def __iter__(self):
        self.current = -len(self.hostname_parts)
        return self

    def __next__(self):
        if self.current > -2:
            raise StopIteration
        else:
            current = self.current
            self.current += 1
            return '.'.join(self.hostname_parts[current:])

    def _is_valid_hostname(self, hostname):
        if hostname[-1] == '.':
            hostname = hostname[:-1]
        if len(hostname) > 253:
            return False
        allowed = re.compile(r'(?!-)[A-Z\d\-\_]{1,63}(?<!-)$', re.IGNORECASE)
        return all(allowed.match(x) for x in hostname.split('.'))


def find_hosted_zone(hostname):
    # TODO: Support pagination for > 100 zones
    hosted_zones = client.list_hosted_zones()['HostedZones']
    if len(hosted_zones) < 1:
        return

    subdomains = SubdomainIterator(hostname)
    for subdomain in subdomains:
        match = [zone for zone in hosted_zones if _compare_record(zone['Name'], subdomain)]
        if match:
            return match[0]


def find_hosted_zone_id(hostname):
    hosted_zone = find_hosted_zone(hostname)
    if hosted_zone:
        return hosted_zone['Id'].split('/')[2]


def get_alias_record(zone_id, record_name):
    record_sets = client.list_resource_record_sets(
        HostedZoneId=zone_id,
        StartRecordName=record_name,
        StartRecordType='A',
        MaxItems='2'
    )
    records = [
        record_set['ResourceRecords'] for record_set in record_sets['ResourceRecordSets'] 
        if _compare_record(record_set['Name'], record_name)
    ]
    # TODO: Support multiple values
    return records[0][0]['Value'] if records else None


def _compare_record(record_name, hostname):
    return '{}.'.format(hostname) == record_name
