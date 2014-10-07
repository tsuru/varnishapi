# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import copy
import os
import unittest

import mock

from feaas import storage
from feaas.managers import cloudstack


class CloudStackManagerTestCase(unittest.TestCase):

    def set_api_envs(self, url="http://cloudstackapi", api_key="key",
                     secret_key="secret"):
        os.environ["CLOUDSTACK_API_URL"] = self.url = url
        os.environ["CLOUDSTACK_API_KEY"] = self.api_key = api_key
        os.environ["CLOUDSTACK_SECRET_KEY"] = self.secret_key = secret_key

    def del_api_envs(self):
        self._remove_envs("CLOUDSTACK_API_URL", "CLOUDSTACK_API_KEY",
                          "CLOUDSTACK_SECRET_KEY")

    def set_vm_envs(self, template_id="abc123", zone_id="zone1",
                    service_offering_id="qwe123", project_id=None,
                    network_id=None):
        os.environ["CLOUDSTACK_TEMPLATE_ID"] = self.template_id = template_id
        self.service_offering_id = service_offering_id
        os.environ["CLOUDSTACK_SERVICE_OFFERING_ID"] = self.service_offering_id
        os.environ["CLOUDSTACK_ZONE_ID"] = self.zone_id = zone_id
        if project_id:
            os.environ["CLOUDSTACK_PROJECT_ID"] = self.project_id = project_id
        if network_id:
            os.environ["CLOUDSTACK_NETWORK_ID"] = self.network_id = network_id

    def del_vm_envs(self):
        self._remove_envs("CLOUDSTACK_TEMPLATE_ID", "CLOUDSTACK_SERVICE_OFFERING_ID",
                          "CLOUDSTACK_ZONE_ID", "CLOUDSTACK_PROJECT_ID",
                          "CLOUDSTACK_NETWORK_ID")

    def _remove_envs(self, *envs):
        for env in envs:
            if env in os.environ:
                del os.environ[env]

    def test_init(self):
        self.set_api_envs()
        self.addCleanup(self.del_api_envs)
        client = cloudstack.CloudStackManager(storage=None)
        self.assertEqual(self.url, client.client.api_url)
        self.assertEqual(self.api_key, client.client.api_key)
        self.assertEqual(self.secret_key, client.client.secret)

    def test_init_no_api_url(self):
        with self.assertRaises(cloudstack.MissConfigurationError) as cm:
            cloudstack.CloudStackManager(storage=None)
        exc = cm.exception
        self.assertEqual(("env var CLOUDSTACK_API_URL is required",),
                         exc.args)

    def test_init_no_api_key(self):
        os.environ["CLOUDSTACK_API_URL"] = "something"
        with self.assertRaises(cloudstack.MissConfigurationError) as cm:
            cloudstack.CloudStackManager(storage=None)
        self.addCleanup(self.del_api_envs)
        exc = cm.exception
        self.assertEqual(("env var CLOUDSTACK_API_KEY is required",),
                         exc.args)

    def test_init_no_secret_key(self):
        os.environ["CLOUDSTACK_API_URL"] = "something"
        os.environ["CLOUDSTACK_API_KEY"] = "not_secret"
        with self.assertRaises(cloudstack.MissConfigurationError) as cm:
            cloudstack.CloudStackManager(storage=None)
        self.addCleanup(self.del_api_envs)
        exc = cm.exception
        self.assertEqual(("env var CLOUDSTACK_SECRET_KEY is required",),
                         exc.args)

    @mock.patch("uuid.uuid4")
    def test_start_instance(self, uuid):
        self.set_api_envs()
        self.addCleanup(self.del_api_envs)
        self.set_vm_envs(project_id="project-123", network_id="net-123")
        self.addCleanup(self.del_vm_envs)
        uuid.return_value = "uuid_val"
        instance = storage.Instance(name="some_instance", units=[])
        strg_mock = mock.Mock()
        strg_mock.retrieve_instance.return_value = instance
        client_mock = mock.Mock()
        client_mock.deployVirtualMachine.return_value = {"id": "abc123",
                                                         "jobid": "qwe321"}
        client_mock.queryAsyncJobResult.return_value = {"jobstatus": 1}
        vm = {"id": "abc123", "nic": [{"ipaddress": "10.0.0.1"}]}
        client_mock.listVirtualMachines.return_value = {"virtualmachine": [vm]}
        client_mock.encode_user_data.return_value = user_data = mock.Mock()
        manager = cloudstack.CloudStackManager(storage=strg_mock)
        manager.client = client_mock
        got_instance = manager.start_instance("some_instance")
        self.assertEqual(instance, got_instance)
        self.assertEqual(1, len(instance.units))
        unit = instance.units[0]
        self.assertEqual("abc123", unit.id)
        self.assertEqual("uuid_val", unit.secret)
        self.assertEqual(instance, unit.instance)
        self.assertEqual("10.0.0.1", unit.dns_name)
        self.assertEqual("creating", unit.state)
        strg_mock.retrieve_instance.assert_called_with(name="some_instance")
        create_data = {"group": "feaas", "templateid": self.template_id,
                       "zoneid": self.zone_id,
                       "serviceofferingid": self.service_offering_id,
                       "userdata": user_data, "networkid": self.network_id,
                       "projectid": self.project_id}
        client_mock.deployVirtualMachine.assert_called_with(create_data)
        actual_user_data = manager.get_user_data("uuid_val")
        client_mock.encode_user_data.assert_called_with(actual_user_data)

    @mock.patch("uuid.uuid4")
    def test_start_instance_no_project_id(self, uuid):
        self.set_api_envs()
        self.addCleanup(self.del_api_envs)
        self.set_vm_envs(network_id="net-123")
        self.addCleanup(self.del_vm_envs)
        uuid.return_value = "uuid_val"
        instance = storage.Instance(name="some_instance", units=[])
        strg_mock = mock.Mock()
        strg_mock.retrieve_instance.return_value = instance
        client_mock = mock.Mock()
        client_mock.deployVirtualMachine.return_value = {"id": "abc123",
                                                         "jobid": "qwe321"}
        client_mock.queryAsyncJobResult.return_value = {"jobstatus": 1}
        vm = {"id": "abc123", "nic": [{"ipaddress": "10.0.0.1"}]}
        client_mock.listVirtualMachines.return_value = {"virtualmachine": [vm]}
        client_mock.encode_user_data.return_value = user_data = mock.Mock()
        manager = cloudstack.CloudStackManager(storage=strg_mock)
        manager.client = client_mock
        got_instance = manager.start_instance("some_instance")
        self.assertEqual(instance, got_instance)
        self.assertEqual(1, len(instance.units))
        unit = instance.units[0]
        self.assertEqual("abc123", unit.id)
        self.assertEqual("uuid_val", unit.secret)
        self.assertEqual(instance, unit.instance)
        self.assertEqual("10.0.0.1", unit.dns_name)
        self.assertEqual("creating", unit.state)
        strg_mock.retrieve_instance.assert_called_with(name="some_instance")
        create_data = {"group": "feaas", "templateid": self.template_id,
                       "zoneid": self.zone_id,
                       "serviceofferingid": self.service_offering_id,
                       "userdata": user_data, "networkid": self.network_id}
        client_mock.deployVirtualMachine.assert_called_with(create_data)
        actual_user_data = manager.get_user_data("uuid_val")
        client_mock.encode_user_data.assert_called_with(actual_user_data)

    @mock.patch("uuid.uuid4")
    def test_start_instance_no_network_id(self, uuid):
        self.set_api_envs()
        self.addCleanup(self.del_api_envs)
        self.set_vm_envs(project_id="proj-123")
        self.addCleanup(self.del_vm_envs)
        uuid.return_value = "uuid_val"
        instance = storage.Instance(name="some_instance", units=[])
        strg_mock = mock.Mock()
        strg_mock.retrieve_instance.return_value = instance
        client_mock = mock.Mock()
        client_mock.deployVirtualMachine.return_value = {"id": "abc123",
                                                         "jobid": "qwe321"}
        client_mock.queryAsyncJobResult.return_value = {"jobstatus": 1}
        vm = {"id": "abc123", "nic": [{"ipaddress": "10.0.0.1"}]}
        client_mock.listVirtualMachines.return_value = {"virtualmachine": [vm]}
        client_mock.encode_user_data.return_value = user_data = mock.Mock()
        manager = cloudstack.CloudStackManager(storage=strg_mock)
        manager.client = client_mock
        got_instance = manager.start_instance("some_instance")
        self.assertEqual(instance, got_instance)
        self.assertEqual(1, len(instance.units))
        unit = instance.units[0]
        self.assertEqual("abc123", unit.id)
        self.assertEqual("uuid_val", unit.secret)
        self.assertEqual(instance, unit.instance)
        self.assertEqual("10.0.0.1", unit.dns_name)
        self.assertEqual("creating", unit.state)
        strg_mock.retrieve_instance.assert_called_with(name="some_instance")
        create_data = {"group": "feaas", "templateid": self.template_id,
                       "zoneid": self.zone_id,
                       "serviceofferingid": self.service_offering_id,
                       "userdata": user_data, "projectid": self.project_id}
        client_mock.deployVirtualMachine.assert_called_with(create_data)
        actual_user_data = manager.get_user_data("uuid_val")
        client_mock.encode_user_data.assert_called_with(actual_user_data)

    def test_start_instance_timeout(self):
        def cleanup():
            del os.environ["CLOUDSTACK_MAX_TRIES"]
        self.addCleanup(cleanup)
        os.environ["CLOUDSTACK_MAX_TRIES"] = "1"
        self.set_api_envs()
        self.addCleanup(self.del_api_envs)
        self.set_vm_envs()
        self.addCleanup(self.del_vm_envs)
        instance = storage.Instance(name="some_instance", units=[])
        strg_mock = mock.Mock()
        strg_mock.retrieve_instance.return_value = instance
        client_mock = mock.Mock()
        client_mock.deployVirtualMachine.return_value = {"id": "abc123",
                                                         "jobid": "qwe321"}
        client_mock.queryAsyncJobResult.return_value = {"jobstatus": 0}
        manager = cloudstack.CloudStackManager(storage=strg_mock)
        manager.client = client_mock
        with self.assertRaises(cloudstack.MaxTryExceededError) as cm:
            manager.start_instance("some_instance")
        exc = cm.exception
        self.assertEqual(1, exc.max_tries)

    def test_terminate_instance(self):
        self.set_api_envs()
        self.addCleanup(self.del_api_envs)
        instance = storage.Instance(name="some_instance",
                                    units=[storage.Unit(id="vm-123"),
                                           storage.Unit(id="vm-456")])
        strg_mock = mock.Mock()
        strg_mock.retrieve_instance.return_value = instance
        manager = cloudstack.CloudStackManager(storage=strg_mock)
        manager.client = client_mock = mock.Mock()
        got_instance = manager.terminate_instance("some_instance")
        self.assertEqual(instance, got_instance)
        expected_calls = [mock.call({"id": "vm-123"}), mock.call({"id": "vm-456"})]
        self.assertEqual(expected_calls, client_mock.destroyVirtualMachine.call_args_list)

    @mock.patch("sys.stderr")
    def test_terminate_instance_ignores_exceptions(self, stderr):
        self.set_api_envs()
        self.addCleanup(self.del_api_envs)
        instance = storage.Instance(name="some_instance",
                                    units=[storage.Unit(id="vm-123"),
                                           storage.Unit(id="vm-456")])
        strg_mock = mock.Mock()
        strg_mock.retrieve_instance.return_value = instance
        client_mock = mock.Mock()
        client_mock.destroyVirtualMachine.side_effect = Exception("wat", "wot")
        manager = cloudstack.CloudStackManager(storage=strg_mock)
        manager.client = client_mock
        got_instance = manager.terminate_instance("some_instance")
        self.assertEqual(instance, got_instance)
        stderr.write.assert_called_with("[ERROR] Failed to terminate CloudStack VM: wat wot")

    @mock.patch("uuid.uuid4")
    def test_physical_scale_up(self, uuid):
        self.set_api_envs()
        self.addCleanup(self.del_api_envs)
        self.set_vm_envs(project_id="project-123", network_id="net-123")
        self.addCleanup(self.del_vm_envs)
        uuid.return_value = "uuid_val"
        instance = storage.Instance(name="some_instance",
                                    units=[storage.Unit(id="123")])
        strg_mock = mock.Mock()
        client_mock = mock.Mock()
        client_mock.deployVirtualMachine.return_value = {"id": "abc123",
                                                         "jobid": "qwe321"}
        client_mock.queryAsyncJobResult.return_value = {"jobstatus": 1}
        vm = {"id": "qwe123", "nic": [{"ipaddress": "10.0.0.5"}]}
        client_mock.listVirtualMachines.return_value = {"virtualmachine": [vm]}
        client_mock.encode_user_data.return_value = user_data = mock.Mock()
        manager = cloudstack.CloudStackManager(storage=strg_mock)
        manager.client = client_mock
        units = manager.physical_scale(instance, 2)
        self.assertEqual(2, len(instance.units))
        self.assertEqual(1, len(units))
        unit = instance.units[1]
        self.assertEqual("qwe123", unit.id)
        self.assertEqual("uuid_val", unit.secret)
        self.assertEqual(instance, unit.instance)
        self.assertEqual("10.0.0.5", unit.dns_name)
        self.assertEqual("creating", unit.state)
        create_data = {"group": "feaas", "templateid": self.template_id,
                       "zoneid": self.zone_id,
                       "serviceofferingid": self.service_offering_id,
                       "userdata": user_data, "networkid": self.network_id,
                       "projectid": self.project_id}
        client_mock.deployVirtualMachine.assert_called_with(create_data)
        actual_user_data = manager.get_user_data("uuid_val")
        client_mock.encode_user_data.assert_called_with(actual_user_data)

    def test_physical_scale_down(self):
        self.set_api_envs()
        self.addCleanup(self.del_api_envs)
        units = [storage.Unit(id="vm-123"), storage.Unit(id="vm-456"),
                 storage.Unit(id="vm-789")]
        instance = storage.Instance(name="some_instance", units=copy.deepcopy(units))
        strg_mock = mock.Mock()
        manager = cloudstack.CloudStackManager(storage=strg_mock)
        manager.client = client_mock = mock.Mock()
        got_units = manager.physical_scale(instance, 1)
        self.assertEqual(1, len(instance.units))
        self.assertEqual(2, len(got_units))
        self.assertEqual("vm-789", instance.units[0].id)
        expected_calls = [mock.call({"id": "vm-123"}), mock.call({"id": "vm-456"})]
        self.assertEqual(expected_calls, client_mock.destroyVirtualMachine.call_args_list)


class MaxTryExceededErrorTestCase(unittest.TestCase):

    def test_error_message(self):
        exc = cloudstack.MaxTryExceededError(40)
        self.assertEqual(40, exc.max_tries)
        self.assertEqual(("exceeded 40 tries",), exc.args)
