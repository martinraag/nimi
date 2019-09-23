# Nimi - Dynamic DNS on AWS

Nimi is yet another self-hosted dynamic DNS solution, built using Python, AWS Route53, Lambda
and API Gateway.

While there are numerous implementations of similar systems available, this project was motivated
by some of the shortcomings of projects I reviewed:

- The setup process is often manual, which is tedious and error prone.
- The clients interact directly with the cloud providers API, requiring appropriate credentials
  to be configured on each host.

Nimi aims to be easy to setup, manage and destroy. The client does not interact with any AWS API's
directly and can be deployed on any host with a bit more peace of mind.

## Installation

```
pip install nimi
```

## Usage

The package will install the `nimi` command line tool, which is used to setup the AWS infrastructure
with CloudFront, add and remove domains from Route53 and configure dynamic DNS hostnames. This
requires valid AWS credentials to be configured.
The subcommand `nimi client` is for use on the hosts added to the system and don't require any AWS
credentials. Instead, it's configured with values generated during the setup.

### Credentials

The `nimi` tool does not accept credentials explicitly and expects them to be configured either in
the environment or configuration file as described in the
[AWS CLI documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html).

### Provision infrastructure

In order to use Nimi, corresponding AWS infrastructure must be provisioned first. This is done
automatically using CloudFormation by invoking the following command.

```
nimi setup
```

### Add a domain

If your domain is already configured in Route53, skip this step. Otherwise run the following command
to create a new hosted zone. Once complete, the output will include a list of name servers, which
you will have to configure with your domain registrar.

```
nimi import <domain>
```

### Add a host

Before running `nimi client`, the desired hostname has to be configured. Invoking the following
command will add the hostname to the configuration and generate a shared secret, that the client
application will use to sign requests sent to the system. The hostname can either be the root domain
or a subdomain of any domain configured in Route53.

```
nimi add <hostname>
```

### Configure client

The `nimi client` subcommands do not need or use any AWS credentials. Instead, the
deployments API URL, desired hostname and shared secret have to be passed as options to the command
or set as environment variables. Each configured hostname must be paired with a unique shared
secret, while the API URL is common between them all. Invoke the following command to view said
information.

```
nimi info
```

Make note of the configured values for the hostname you added. The mapping of values to environment
variables and command line options are marked below.

| Value         | Environment   | Option   |
| ------------- | ------------- | -------- |
| API URL       | NIMI_URL      | URL      |
| Hostname      | NIMI_HOSTNAME | HOSTNAME |
| Shared Secret | NIMI_SECRET   | SECRET   |

Set the required environment variables and run the following command on the host you want to enable
dynamic DNS for.

```
nimi client ping
```

Alternatively pass the values as command line options.

```
nimi client ping URL HOSTNAME SECRET
```

The `ping` command sends a single request to the provisioned backend. The payload includes the
desired hostname and its HMAC-SHA256 hash created using the shared secret. The backend will validate
the request by comparing the hash and update the corresponding DNS `A` record if the source IP
address has changed.

### Running client periodically

The `ping` command should be run periodically on the host to ensure the DNS records stay up to date.
The client currently has no means to setup periodic execution automatically.
Users should schedule the command to be executed at a desired interval using tools available on
the hosts platform, i.e. [Cron](https://help.ubuntu.com/community/CronHowto) on Linux or
[launchd](https://www.launchd.info) on Mac OS.

### Cleanup

If you wish to stop using the system, the `nimi` command line tool includes commands to delete
anything you configured with it.

Remove a configured hostname, any subsequent pings will have no effect.

```
nimi remove <hostname>
```

Remove a domain from Route53 and all associated hostnames.

```
nimi eject <domain>
```

Completely remove provisioned AWS infrastructure. Does not remove any domains from Route53.

```
nimi destroy
```

## Cost

For personal use, the cost of running the system should be neglieble, but not completely free.
AWS Lambda includes a [geneours free tier](https://aws.amazon.com/lambda/pricing/) with up to
a million requests per month for free and your usage should stay well within those limits.

API Gateways free tier is only valid for the first 12 months of the account, but for a small
deployment [the pricing](https://aws.amazon.com/api-gateway/pricing/) is reasonable and usually
comes to about \$0.02 per month for a deployment with a couple of hosts pinging every 5 to 10
minutes.

The most costly part of the deployment is [Route53](https://aws.amazon.com/route53/pricing/),
which charges \$0.50 per hosted zone (domain), as well as for DNS queries served, though for a
personal deployment the latter should be small enough to not be reflected in the bill.

There is no reason the system couldn't support other DNS providers that are cheaper or free, if
you'd like to extend support feel free to contribute.
