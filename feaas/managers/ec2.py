# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os
import urlparse
import uuid
import sys
from httplib2 import Http

from feaas import storage

from . import BaseManager

DUMP_VCL_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                             "misc", "dump_vcls.bash"))


class EC2Manager(BaseManager):

    def __init__(self, *args, **kwargs):
        super(EC2Manager, self).__init__(*args, **kwargs)
        self._connection = None

    @property
    def connection(self):
        if not self._connection:
            self._connection = self._connect()
        return self._connection

    def _connect(self):
        endpoint = os.environ.get("EC2_ENDPOINT", "https://ec2.sa-east-1.amazonaws.com")
        access_key = os.environ.get("EC2_ACCESS_KEY")
        secret_key = os.environ.get("EC2_SECRET_KEY")
        from boto import ec2
        url = urlparse.urlparse(endpoint)
        scheme = url.scheme
        host_port = url.netloc.split(":")
        host = host_port[0]
        if len(host_port) > 1:
            port = int(host_port[1])
        else:
            port = 80 if scheme == "http" else 443
        path = url.path or "/"
        region = ec2.RegionInfo(name="custom", endpoint=host)
        return ec2.EC2Connection(aws_access_key_id=access_key,
                                 aws_secret_access_key=secret_key,
                                 host=host, port=port,
                                 is_secure=scheme == "https",
                                 path=path, region=region)

    def start_instance(self, name):
        instance = self.storage.retrieve_instance(name=name)
        self._add_units(instance, 1)
        return instance

    def _run_unit(self):
        ami_id = os.environ.get("AMI_ID")
        subnet_id = os.environ.get("SUBNET_ID")
        secret = unicode(uuid.uuid4())
        reservation = self.connection.run_instances(image_id=ami_id,
                                                    subnet_id=subnet_id,
                                                    user_data=self._user_data(secret))
        ec2_instance = reservation.instances[0]
        return storage.Unit(id=ec2_instance.id, dns_name=ec2_instance.dns_name,
                            secret=secret, state="creating")

    def _user_data(self, secret):
        if "USER_DATA_URL" in os.environ:
            url = os.environ.get("USER_DATA_URL")
            h = Http()
            (resp, user_data) = h.request(url)
            return user_data.replace("VARNISH_SECRET_KEY", secret)
        user_data_lines = None
        packages = os.environ.get("API_PACKAGES")
        if packages:
            user_data_lines = ["apt-get update",
                               "apt-get install -y {0}".format(packages),
                               "sed -i -e 's/-T localhost:6082/-T :6082/' /etc/default/varnish",
                               "sed -i -e 's/-a :6081/-a :8080/' /etc/default/varnish",
                               "echo {0} > /etc/varnish/secret".format(secret),
                               "service varnish restart",
                               "cat > /etc/cron.hourly/dump_vcls <<'END'",
                               open(DUMP_VCL_FILE).read(),
                               "END",
                               "chmod +x /etc/cron.hourly/dump_vcls"]
        if user_data_lines:
            return "\n".join(user_data_lines) + "\n"

    def terminate_instance(self, name):
        instance = self.storage.retrieve_instance(name=name)
        for unit in instance.units:
            self._terminate_unit(unit)
        return instance

    def _terminate_unit(self, unit):
        try:
            self.connection.terminate_instances(instance_ids=[unit.id])
        except Exception as e:
            sys.stderr.write("[ERROR] Failed to terminate EC2 instance: %s" %
                             " ".join([str(arg) for arg in e.args]))

    def physical_scale(self, instance, quantity):
        new_units = quantity - len(instance.units)
        if new_units < 0:
            return self._remove_units(instance, -1 * new_units)
        return self._add_units(instance, new_units)

    def _add_units(self, instance, quantity):
        units = []
        for i in xrange(quantity):
            unit = self._run_unit()
            instance.add_unit(unit)
            units.append(unit)
        self.storage.store_instance(instance)
        return units

    def _remove_units(self, instance, quantity):
        units = []
        for i in xrange(quantity):
            self._terminate_unit(instance.units[i])
            units.append(instance.units[i])
        for unit in units:
            instance.remove_unit(unit)
        self.storage.store_instance(instance)
        return units
