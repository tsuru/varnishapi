# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os
import urlparse
import syslog

from varnishapi import storage


class EC2Manager(object):

    def __init__(self, _storage=None):
        self._connection = None
        self.storage = _storage or storage.DumbStorage()

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
        return ec2.EC2Connection(aws_access_key_id=access_key,
                                 aws_secret_access_key=secret_key,
                                 host=host, port=port,
                                 is_secure=scheme == "https",
                                 path=path)

    def add_instance(self, name):
        key_path = os.environ.get("KEY_PATH", os.path.expanduser("~/.ssh/id_rsa.pub"))
        ami_id = os.environ.get("AMI_ID")
        subnet_id = os.environ.get("SUBNET_ID")
        key = ""
        with open(key_path) as key_file:
            key = key_file.read()
        user_data = """#cloud-config
ssh_authorized_keys: ['{0}']
""".format(key)
        reservation = None
        try:
            reservation = self.connection.run_instances(image_id=ami_id,
                                                        subnet_id=subnet_id,
                                                        user_data=user_data)
            for instance in reservation.instances:
                self.storage.store(instance_id=instance.id,
                                   dns_name=instance.dns_name,
                                   name=name)
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, "Failed to create EC2 instance: %s" %
                          e.message)
        return reservation

    def bind(self, name):
        pass

    def unbind(self):
        pass

    def remove_instance(self, name):
        instance_id = self.storage.retrieve(name=name)
        try:
            self.connection.terminate_instances(instance_ids=[instance_id])
            self.storage.remove(name=name)
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, "Failed to terminate EC2 instance: %s" %
                          e.message)

    def is_ok(self):
        return True, ""
