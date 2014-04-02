# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os
import urlparse
import sys

import varnish
from feaas import storage

VCL_TEMPLATE = (r""" "director app dns {{ {{ .backend = {{ .host = \"{0}\"; """
                r""".port = \"80\"; }} }} .ttl = 5m; }}" """)


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
        ami_id = os.environ.get("AMI_ID")
        subnet_id = os.environ.get("SUBNET_ID")
        reservation = None
        try:
            reservation = self.connection.run_instances(image_id=ami_id,
                                                        subnet_id=subnet_id,
                                                        user_data=self._user_data())
            for instance in reservation.instances:
                self.storage.store(storage.Instance(id=instance.id,
                                                    dns_name=instance.dns_name,
                                                    name=name))
        except Exception as e:
            sys.stderr.write("[ERROR] Failed to create EC2 instance: %s" %
                             " ".join(e.args))
        return reservation

    def _user_data(self):
        user_data_lines = []
        user_data_lines.extend(self._packages())
        if user_data_lines:
            return "\n".join(user_data_lines) + "\n"

    def _packages(self):
        packages = os.environ.get("API_PACKAGES")
        if packages:
            return ["apt-get update",
                    "apt-get install -y {0}".format(packages)]
        return []

    def bind(self, name, app_host):
        instance_addr = self._get_instance_addr(name)
        self.write_vcl(instance_addr, app_host)

    def unbind(self, name, app_host):
        instance_addr = self._get_instance_addr(name)
        self.remove_vcl(instance_addr)

    def _get_instance_addr(self, name):
        instance = self.storage.retrieve(name=name)
        reservations = self.connection.get_all_instances(instance_ids=[instance.id])
        if len(reservations) == 0 or len(reservations[0].instances) == 0:
            raise storage.InstanceNotFoundError()
        return reservations[0].instances[0].private_ip_address

    def write_vcl(self, instance_addr, app_addr):
        secret = os.environ.get("SECRET")
        vcl = self.vcl_template().format(app_addr)
        handler = varnish.VarnishHandler("{0}:6082".format(instance_addr),
                                         secret=secret)
        handler.vcl_inline("feaas", vcl)
        handler.vcl_use("feaas")
        handler.quit()

    def remove_vcl(self, instance_addr):
        secret = os.environ.get("SECRET")
        handler = varnish.VarnishHandler("{0}:6082".format(instance_addr),
                                         secret=secret)
        handler.vcl_use("boot")
        handler.vcl_discard("feaas")
        handler.quit()

    def vcl_template(self):
        return VCL_TEMPLATE

    def remove_instance(self, name):
        instance = self.storage.retrieve(name=name)
        try:
            self.connection.terminate_instances(instance_ids=[instance.id])
            self.storage.remove(name=name)
        except Exception as e:
            sys.stderr.write("[ERROR] Failed to terminate EC2 instance: %s" %
                             " ".join(e.args))

    def info(self, name):
        return self.storage.retrieve(name).to_dict()

    def status(self, name):
        instance = self.storage.retrieve(name)
        reservations = self.connection.get_all_instances(instance_ids=[instance.id])
        if len(reservations) < 1 or len(reservations[0].instances) < 1:
            raise storage.InstanceNotFoundError()
        return reservations[0].instances[0].state
