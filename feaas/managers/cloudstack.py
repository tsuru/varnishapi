# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os

from feaas import managers

from .cloudstack_client import CloudStack


class CloudStackManager(managers.BaseManager):

    def __init__(self, *args, **kwargs):
        super(CloudStackManager, self).__init__(*args, **kwargs)
        url = self.get_env("CLOUDSTACK_API_URL")
        key = self.get_env("CLOUDSTACK_API_KEY")
        secret_key = self.get_env("CLOUDSTACK_SECRET_KEY")
        self.client = CloudStack(url, key, secret_key)

    def get_env(self, name):
        try:
            return os.environ[name]
        except KeyError:
            raise MissConfigurationError("env var {} is required".format(name))

    def start_instance(self, name):
        raise NotImplementedError()

    def terminate_instance(self, name):
        raise NotImplementedError()

    def physical_scale(self, instance, quantity):
        raise NotImplementedError()


class MissConfigurationError(Exception):
    pass
