# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import cStringIO as StringIO
import os
import urlparse
import subprocess
import sys

from feaas import storage

VCL_TEMPLATE = """backend default {{
    .host = \\"{0}\\";
    .port = \\"80\\";
}}
"""


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
        ssh_path = os.environ.get("SSH_PATH", "/home/ubuntu/.ssh")
        key = self._read_key()
        if key:
            user_data_lines.extend(["mkdir -p {0}".format(ssh_path),
                                    "cat >> {0}/authorized_keys <<END".format(ssh_path),
                                    key, "END"])
        user_data_lines.extend(self._packages())
        if user_data_lines:
            return "\n".join(user_data_lines) + "\n"

    def _read_key(self):
        if os.environ.get("LOAD_KEY_FROM_STORAGE"):
            return self.storage.retrieve_public_key()
        key_path = os.environ.get("KEY_PATH")
        if key_path:
            with open(key_path) as key_file:
                return key_file.read()

    def _packages(self):
        packages = os.environ.get("API_PACKAGES")
        if packages:
            return ["apt-get update",
                    "apt-get install -y {0}".format(packages)]
        return []

    def bind(self, name, app_host):
        self._set_backend(name, app_host)

    def unbind(self, name, app_host):
        self._set_backend(name, "localhost")

    def _set_backend(self, name, backend):
        instance = self.storage.retrieve(name=name)
        reservations = self.connection.get_all_instances(instance_ids=[instance.id])
        if len(reservations) == 0 or len(reservations[0].instances) == 0:
            raise storage.InstanceNotFoundError()
        instance_ip = reservations[0].instances[0].private_ip_address
        self.write_vcl(instance_ip, backend)

    def write_vcl(self, instance_addr, app_addr):
        out = StringIO.StringIO()
        cmd = 'sudo bash -c "echo \'{0}\' > /etc/varnish/default.vcl && service varnish reload"'
        cmd = cmd.format(self.vcl_template().format(app_addr))
        user = os.environ.get("SSH_USER", "ubuntu")
        exit_status = subprocess.call(["ssh", instance_addr, "-l", user,
                                       "-o", "StrictHostKeyChecking no", cmd],
                                      stdout=out, stderr=out)
        out.seek(0)
        out = out.read()
        if exit_status != 0:
            msg = "[ERROR] Failed to write VCL file in the instance {0}: {1}"
            sys.stderr.write(msg.format(instance_addr, out))
            raise Exception("Could not connect to the service instance")

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
