import re
import boto3


# The following functions are imported here from the handler, instead of the other way around,
# as it enables a simplified Lambda function deployment. By keeping the Lambda function a single
# file, we don't need to package the modules for deployment or create an S3 bucket for storing said
# package, which would become useless after the initial setup.
from nimi.handler import get_alias_record, compare_record


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
        match = [zone for zone in hosted_zones if compare_record(zone['Name'], subdomain)]
        if match:
            return match[0]


def find_hosted_zone_id(hostname):
    hosted_zone = find_hosted_zone(hostname)
    if hosted_zone:
        return hosted_zone['Id'].split('/')[2]
