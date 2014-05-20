# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import codecs
import os
import urlparse
import uuid
import sys

import varnish
from feaas import storage

VCL_TEMPLATE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                                 "misc", "default.vcl"))
DUMP_VCL_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                             "misc", "dump_vcls.bash"))


class EC2Manager(object):

    def __init__(self, storage):
        self._connection = None
        self.storage = storage

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

    def add_instance(self, name):
        self._check_duplicate(name)
        instance = storage.Instance(name)
        self.storage.store_instance(instance)
        return instance

    def _check_duplicate(self, name):
        try:
            self.storage.retrieve_instance(name)
            raise storage.InstanceAlreadyExistsError()
        except storage.InstanceNotFoundError:
            pass

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

    def bind(self, name, app_host):
        instance = self.storage.retrieve_instance(name=name)
        bind = storage.Bind(app_host, instance)
        self.storage.store_bind(bind)

    def unbind(self, name, app_host):
        instance = self.storage.retrieve_instance(name=name)
        for unit in instance.units:
            self.remove_vcl(unit.dns_name, unit.secret)
        bind = storage.Bind(app_host, instance)
        self.storage.remove_bind(bind)

    def write_vcl(self, instance_addr, secret, app_addr):
        vcl = self.vcl_template() % {"app_host": app_addr}
        handler = varnish.VarnishHandler("{0}:6082".format(instance_addr),
                                         secret=secret)
        handler.vcl_inline("feaas", vcl.encode("iso-8859-1", "ignore"))
        handler.vcl_use("feaas")
        handler.quit()

    def remove_vcl(self, instance_addr, secret):
        handler = varnish.VarnishHandler("{0}:6082".format(instance_addr),
                                         secret=secret)
        handler.vcl_use("boot")
        handler.vcl_discard("feaas")
        handler.quit()

    def vcl_template(self):
        with codecs.open(VCL_TEMPLATE_FILE, encoding="utf-8") as f:
            content = f.read()
            content = content.replace("\n", " ")
            content = content.replace('"', r'\"')
            content = content.replace("\t", "")
            return '"%s"' % content.strip()

    def remove_instance(self, name):
        instance = self.storage.retrieve_instance(name=name)
        for unit in instance.units:
            self._terminate_unit(unit)
        self.storage.remove_instance(name=name)

    def _terminate_unit(self, unit):
        try:
            self.connection.terminate_instances(instance_ids=[unit.id])
        except Exception as e:
            sys.stderr.write("[ERROR] Failed to terminate EC2 instance: %s" %
                             " ".join([str(arg) for arg in e.args]))

    def info(self, name):
        instance = self.storage.retrieve_instance(name)
        return [{"label": "Address",
                 "value": instance.units[0].dns_name}]

    def status(self, name):
        instance = self.storage.retrieve_instance(name)
        reservations = self.connection.get_all_instances(instance_ids=[instance.units[0].id])
        if len(reservations) < 1 or len(reservations[0].instances) < 1:
            raise storage.InstanceNotFoundError()
        return reservations[0].instances[0].state

    def scale_instance(self, name, quantity):
        if quantity < 1:
            raise ValueError("quantity must be a positive integer")
        instance = self.storage.retrieve_instance(name)
        new_units = quantity - len(instance.units)
        if new_units == 0:
            raise ValueError("instance already have %d units" % quantity)
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
