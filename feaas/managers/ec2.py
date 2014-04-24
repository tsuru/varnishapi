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
        ami_id = os.environ.get("AMI_ID")
        subnet_id = os.environ.get("SUBNET_ID")
        reservation = None
        secret = unicode(uuid.uuid4())
        try:
            reservation = self.connection.run_instances(image_id=ami_id,
                                                        subnet_id=subnet_id,
                                                        user_data=self._user_data(secret))
            for instance in reservation.instances:
                self.storage.store(storage.Instance(id=instance.id,
                                                    dns_name=instance.dns_name,
                                                    name=name, secret=secret))
        except Exception as e:
            sys.stderr.write("[ERROR] Failed to create EC2 instance: %s" %
                             " ".join(e.args))
        return reservation

    def _check_duplicate(self, name):
        try:
            self.storage.retrieve(name)
            raise storage.InstanceAlreadyExistsError()
        except storage.InstanceNotFoundError:
            pass

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
        instance_addr, secret = self.get_instance_addr(name)
        self.write_vcl(instance_addr, secret, app_host)

    def unbind(self, name, app_host):
        instance_addr, secret = self.get_instance_addr(name)
        self.remove_vcl(instance_addr, secret)

    def get_instance_addr(self, name):
        instance = self.storage.retrieve(name=name)
        return instance.dns_name, instance.secret

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
        instance = self.storage.retrieve(name=name)
        try:
            self.connection.terminate_instances(instance_ids=[instance.id])
            self.storage.remove(name=name)
        except Exception as e:
            sys.stderr.write("[ERROR] Failed to terminate EC2 instance: %s" %
                             " ".join([str(arg) for arg in e.args]))

    def info(self, name):
        instance = self.storage.retrieve(name)
        return [{"label": "Address", "value": instance.dns_name}]

    def status(self, name):
        instance = self.storage.retrieve(name)
        reservations = self.connection.get_all_instances(instance_ids=[instance.id])
        if len(reservations) < 1 or len(reservations[0].instances) < 1:
            raise storage.InstanceNotFoundError()
        return reservations[0].instances[0].state
