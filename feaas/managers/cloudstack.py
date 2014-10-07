# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os
import sys
import time
import uuid

from feaas import managers, storage

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
        instance = self.storage.retrieve_instance(name=name)
        self._add_units(instance, 1)
        return instance

    def terminate_instance(self, name):
        instance = self.storage.retrieve_instance(name=name)
        for unit in instance.units:
            self._destroy_vm(unit)
        return instance

    def physical_scale(self, instance, quantity):
        new_units = quantity - len(instance.units)
        if new_units < 0:
            return self._remove_units(instance, -1 * new_units)
        return self._add_units(instance, new_units)

    def _add_units(self, instance, quantity):
        units = []
        for i in xrange(quantity):
            unit = self._deploy_vm(instance)
            instance.add_unit(unit)
            units.append(unit)
        self.storage.store_instance(instance)
        return units

    def _deploy_vm(self, instance):
        secret = unicode(uuid.uuid4())
        group = os.environ.get("CLOUDSTACK_GROUP", "feaas")
        data = {
            "group": group,
            "templateid": self.get_env("CLOUDSTACK_TEMPLATE_ID"),
            "zoneid": self.get_env("CLOUDSTACK_ZONE_ID"),
            "serviceofferingid": self.get_env("CLOUDSTACK_SERVICE_OFFERING_ID"),
            "userdata": self.client.encode_user_data(self.get_user_data(secret)),
        }
        project_id = os.environ.get("CLOUDSTACK_PROJECT_ID")
        if project_id:
            data["projectid"] = project_id
        network_id = os.environ.get("CLOUDSTACK_NETWORK_ID")
        if network_id:
            data["networkids"] = network_id
        vm_job = self.client.deployVirtualMachine(data)
        max_tries = int(os.environ.get("CLOUDSTACK_MAX_TRIES", 100))
        vm = self._wait_for_unit(vm_job, max_tries, project_id)
        return storage.Unit(id=vm["id"], dns_name=vm["nic"][0]["ipaddress"],
                            state="creating", secret=secret)

    def _wait_for_unit(self, vm_job, max_tries, project_id):
        status = 0
        tries = 0
        job_id = vm_job["jobid"]
        while tries < max_tries:
            result = self.client.queryAsyncJobResult({"jobid": job_id})
            status = result["jobstatus"]
            if status != 0:
                break
            time.sleep(1)
            tries += 1
        if status == 0:
            raise MaxTryExceededError(max_tries)
        data = {"id": vm_job["id"]}
        if project_id:
            data["projectid"] = project_id
        vms = self.client.listVirtualMachines(data)
        return vms["virtualmachine"][0]

    def _remove_units(self, instance, quantity):
        units = []
        for i in xrange(quantity):
            self._destroy_vm(instance.units[i])
            units.append(instance.units[i])
        for unit in units:
            instance.remove_unit(unit)
        self.storage.store_instance(instance)
        return units

    def _destroy_vm(self, unit):
        try:
            self.client.destroyVirtualMachine({"id": unit.id})
        except Exception as e:
            sys.stderr.write("[ERROR] Failed to terminate CloudStack VM: %s" %
                             " ".join([str(arg) for arg in e.args]))


class MissConfigurationError(Exception):
    pass


class MaxTryExceededError(Exception):

    def __init__(self, max_tries):
        self.max_tries = max_tries
        msg = "exceeded {0} tries".format(max_tries)
        super(MaxTryExceededError, self).__init__(msg)
