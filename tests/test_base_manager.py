# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import unittest

import mock

from feaas import managers, storage as api_storage


class BaseManagerTestCase(unittest.TestCase):

    def setUp(self):
        self.manager = managers.BaseManager(None)

    def test_new_instance(self):
        storage = mock.Mock()
        storage.retrieve_instance.side_effect = api_storage.InstanceNotFoundError()
        manager = managers.BaseManager(storage)
        instance = manager.new_instance("someapp")
        storage.store_instance.assert_called_with(instance)

    def test_new_duplicate_instance(self):
        storage = mock.Mock()
        storage.retrieve_instance.return_value = "instance"
        manager = managers.BaseManager(storage)
        with self.assertRaises(api_storage.InstanceAlreadyExistsError):
            manager.new_instance("pull")

    @mock.patch("feaas.storage.Bind")
    def test_bind_instance(self, Bind):
        Bind.return_value = "abacaxi"
        instance = api_storage.Instance(name="myinstance",
                                        units=[api_storage.Unit(secret="abc-123",
                                                                dns_name="10.1.1.2",
                                                                id="i-0800")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = managers.BaseManager(storage)
        manager.bind("someapp", "myapp.cloud.tsuru.io")
        storage.retrieve_instance.assert_called_with(name="someapp")
        storage.store_bind.assert_called_with("abacaxi")
        Bind.assert_called_with("myapp.cloud.tsuru.io", instance)

    @mock.patch("feaas.storage.Bind")
    def test_unbind_instance(self, Bind):
        Bind.return_value = "abacaxi"
        instance = api_storage.Instance(name="myinstance",
                                        units=[api_storage.Unit(id="i-0800",
                                                                secret="abc-123",
                                                                dns_name="10.1.1.2")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = managers.BaseManager(storage)
        remove_vcl = mock.Mock()
        manager.remove_vcl = remove_vcl
        manager.unbind("someapp", "myapp.cloud.tsuru.io")
        storage.retrieve_instance.assert_called_with(name="someapp")
        storage.remove_bind.assert_called_with("abacaxi")
        Bind.assert_called_with("myapp.cloud.tsuru.io", instance)
        remove_vcl.assert_called_with("10.1.1.2", "abc-123")

    def test_vcl_template(self):
        manager = managers.BaseManager(None)
        with open(managers.VCL_TEMPLATE_FILE) as f:
            content = f.read().replace("\n", " ").replace('"', r'\"')
            content = content.replace("\t", "")
            self.assertEqual('"%s"' % content.strip(),
                             manager.vcl_template())

    @mock.patch("varnish.VarnishHandler")
    def test_write_vcl(self, VarnishHandler):
        varnish_handler = mock.Mock()
        VarnishHandler.return_value = varnish_handler
        app_host, instance_ip = "yeah.cloud.tsuru.io", "10.2.1.2"
        manager = managers.BaseManager(None)
        manager.write_vcl(instance_ip, "abc-def", app_host)
        vcl = manager.vcl_template() % {"app_host": app_host}
        VarnishHandler.assert_called_with("{0}:6082".format(instance_ip),
                                          secret="abc-def")
        varnish_handler.vcl_inline.assert_called_with("feaas", vcl)
        varnish_handler.vcl_use.assert_called_with("feaas")
        varnish_handler.quit.assert_called()

    @mock.patch("varnish.VarnishHandler")
    def test_write_vcl_ignores_106(self, VarnishHandler):
        varnish_handler = mock.Mock()
        exc = AssertionError("106 Already a VCL program named feaas")
        varnish_handler.vcl_inline.side_effect = exc
        VarnishHandler.return_value = varnish_handler
        app_host, instance_ip = "yeah.cloud.tsuru.io", "10.2.1.2"
        manager = managers.BaseManager(None)
        manager.write_vcl(instance_ip, "abc-def", app_host)

    @mock.patch("varnish.VarnishHandler")
    def test_write_vcl_doesnt_swallow_exceptions_that_arent_106(self, VarnishHandler):
        varnish_handler = mock.Mock()
        exc = AssertionError("Something went wrong")
        varnish_handler.vcl_inline.side_effect = exc
        VarnishHandler.return_value = varnish_handler
        app_host, instance_ip = "yeah.cloud.tsuru.io", "10.2.1.2"
        manager = managers.BaseManager(None)
        with self.assertRaises(AssertionError) as cm:
            manager.write_vcl(instance_ip, "abc-def", app_host)
        exc = cm.exception
        self.assertEqual(("Something went wrong",), exc.args)

    @mock.patch("varnish.VarnishHandler")
    def test_remove_vcl(self, VarnishHandler):
        varnish_handler = mock.Mock()
        VarnishHandler.return_value = varnish_handler
        instance_ip = "10.2.2.1"
        manager = managers.BaseManager(None)
        manager.remove_vcl(instance_ip, "abc123")
        VarnishHandler.assert_called_with("10.2.2.1:6082", secret="abc123")
        varnish_handler.vcl_use.assert_called_with("boot")
        varnish_handler.vcl_discard.assert_called_with("feaas")
        varnish_handler.quit.assert_called()

    def test_info(self):
        instance = api_storage.Instance(name="secret",
                                        units=[api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                                                id="i-0800")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = managers.BaseManager(storage)
        expected = [{"label": "Address", "value": "secret.cloud.tsuru.io"}]
        self.assertEqual(expected, manager.info("secret"))
        storage.retrieve_instance.assert_called_with(name="secret")

    def test_info_multiple_units(self):
        units = [api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                  id="i-0800"),
                 api_storage.Unit(dns_name="not-secret.cloud.tsuru.io",
                                  id="i-0800")]
        instance = api_storage.Instance(name="secret", units=units)
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = managers.BaseManager(storage)
        expected = [{"label": "Address", "value": "secret.cloud.tsuru.io"}]
        self.assertEqual(expected, manager.info("secret"))
        storage.retrieve_instance.assert_called_with(name="secret")

    def test_info_instance_not_found(self):
        storage = mock.Mock()
        storage.retrieve_instance.side_effect = api_storage.InstanceNotFoundError()
        manager = managers.BaseManager(storage)
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.info("secret")

    def test_status(self):
        instance = api_storage.Instance(name="secret", state="started",
                                        units=[api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                                                id="i-0800")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = managers.BaseManager(storage)
        status = manager.status("secret")
        self.assertEqual("started", status)

    def test_status_instance_not_found_in_storage(self):
        storage = mock.Mock()
        storage.retrieve_instance.side_effect = api_storage.InstanceNotFoundError()
        manager = managers.BaseManager(storage)
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.status("secret")

    def test_scale_instance(self):
        instance = api_storage.Instance(name="secret", state="started")
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = managers.BaseManager(storage)
        manager.scale_instance("secret", 2)
        storage.store_scale_job.assert_called_with({"instance": "secret",
                                                    "quantity": 2,
                                                    "state": "pending"})

    def test_scale_instance_already_scaling(self):
        instance = api_storage.Instance(name="secret", state="scaling")
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = managers.BaseManager(storage)
        with self.assertRaises(ValueError) as cm:
            manager.scale_instance("secret", 2)
        exc = cm.exception
        self.assertEqual(("instance is already scaling",), exc.args)

    def test_scale_instance_no_change(self):
        instance = api_storage.Instance(name="secret",
                                        units=[api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                                                id="i-0800"),
                                               api_storage.Unit(dns_name="secreti.cloud.tsuru.io",
                                                                id="i-0801")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = managers.BaseManager(storage)
        with self.assertRaises(ValueError) as cm:
            manager.scale_instance("secret", 2)
        exc = cm.exception
        self.assertEqual(("instance already have 2 units",), exc.args)
        storage.retrieve_instance.assert_called_with(name="secret")

    def test_scale_instance_negative_quantity(self):
        manager = managers.BaseManager(None)
        with self.assertRaises(ValueError) as cm:
            manager.scale_instance("myapp", -1)
        exc = cm.exception
        self.assertEqual(("quantity must be a positive integer",), exc.args)

    def test_scale_instance_zero_quantity(self):
        manager = managers.BaseManager(None)
        with self.assertRaises(ValueError) as cm:
            manager.scale_instance("myapp", 0)
        exc = cm.exception
        self.assertEqual(("quantity must be a positive integer",), exc.args)

    def test_start_instance(self):
        with self.assertRaises(NotImplementedError):
            self.manager.start_instance("something")

    def test_terminate_instance(self):
        with self.assertRaises(NotImplementedError):
            self.manager.terminate_instance("something")

    def test_physical_scale(self):
        with self.assertRaises(NotImplementedError):
            self.manager.physical_scale("something", 10)
