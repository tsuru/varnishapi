# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import threading
import time
import unittest

import mock

from feaas import storage, vcl_writer


class VCLWriterTestCase(unittest.TestCase):

    def test_init(self):
        strg = storage.MongoDBStorage()
        manager = mock.Mock(storage=strg)
        writer = vcl_writer.VCLWriter(manager, interval=10, max_items=3)
        self.assertEqual(manager, writer.manager)
        self.assertEqual(strg, writer.storage)
        self.assertEqual(10, writer.interval)
        self.assertEqual(3, writer.max_items)

    def test_loop(self):
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        fake_run = mock.Mock()
        writer = vcl_writer.VCLWriter(manager, interval=3, max_items=3)
        writer.run = fake_run
        t = threading.Thread(target=writer.loop)
        t.start()
        time.sleep(1)
        writer.stop()
        t.join()
        fake_run.assert_called()
        expected_calls = [mock.call(vcl_writer.UNITS_LOCKER),
                          mock.call(vcl_writer.BINDS_LOCKER)]
        self.assertEqual(expected_calls, strg.init_locker.call_args_list)

    def test_stop(self):
        manager = mock.Mock(storage=None)
        writer = vcl_writer.VCLWriter(manager)
        writer.running = True
        writer.stop()
        self.assertFalse(writer.running)

    def test_run(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802")]
        strg = mock.Mock()
        strg.load_units.return_value = units
        manager = mock.Mock(storage=strg)
        writer = vcl_writer.VCLWriter(manager, max_items=3)
        writer._is_unit_up = lambda unit: unit == units[1]
        writer.bind_units = mock.Mock()
        writer.run()
        strg.lock.assert_called_with(vcl_writer.UNITS_LOCKER)
        strg.load_units.assert_called_with(state="creating", limit=3)
        strg.unlock.assert_called_with(vcl_writer.UNITS_LOCKER)
        writer.bind_units.assert_called_with([units[1]])
        strg.update_units.assert_called_with([units[1]], state="started")

    def test_bind_units(self):
        instance1 = storage.Instance(name="myinstance")
        instance2 = storage.Instance(name="yourinstance")
        units = [storage.Unit(dns_name="instance1-1.cloud.tsuru.io", id="i-0800",
                              instance=instance1, secret="abc123"),
                 storage.Unit(dns_name="instance1-2.cloud.tsuru.io", id="i-0801",
                              instance=instance1, secret="abc321"),
                 storage.Unit(dns_name="instance2-1.cloud.tsuru.io", id="i-0802",
                              instance=instance2, secret="abc456")]
        strg = mock.Mock()
        strg.load_units.return_value = units
        strg.retrieve_binds.return_value = [storage.Bind("myapp.cloud.tsuru.io",
                                                         instance1)]
        manager = mock.Mock(storage=strg)
        writer = vcl_writer.VCLWriter(manager, max_items=3)
        writer.bind_units(units)
        expected_calls = [mock.call("myinstance"), mock.call("yourinstance")]
        self.assertEqual(expected_calls, strg.retrieve_binds.call_args_list)
        expected_calls = [mock.call("instance1-1.cloud.tsuru.io", "abc123",
                                    "myapp.cloud.tsuru.io"),
                          mock.call("instance1-2.cloud.tsuru.io", "abc321",
                                    "myapp.cloud.tsuru.io"),
                          mock.call("instance2-1.cloud.tsuru.io", "abc456",
                                    "myapp.cloud.tsuru.io")]
        self.assertEqual(expected_calls, manager.write_vcl.call_args_list)

    @mock.patch("telnetlib.Telnet")
    def test_is_unit_up_up(self, Telnet):
        telnet_client = mock.Mock()
        Telnet.return_value = telnet_client
        unit = storage.Unit(dns_name="instance1.cloud.tsuru.io")
        manager = mock.Mock(storage=None)
        writer = vcl_writer.VCLWriter(manager, max_items=3)
        self.assertTrue(writer._is_unit_up(unit))
        Telnet.assert_called_with(unit.dns_name, "6082", timeout=3)
        telnet_client.close.assert_called_once()

    @mock.patch("telnetlib.Telnet")
    def test_is_unit_up_down(self, Telnet):
        Telnet.side_effect = ValueError()
        unit = storage.Unit(dns_name="instance1.cloud.tsuru.io")
        manager = mock.Mock(storage=storage.MongoDBStorage())
        writer = vcl_writer.VCLWriter(manager, max_items=3)
        self.assertFalse(writer._is_unit_up(unit))
        Telnet.assert_called_with(unit.dns_name, "6082", timeout=3)
