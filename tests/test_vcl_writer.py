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
        writer.locker = mock.Mock()
        t = threading.Thread(target=writer.loop)
        t.start()
        time.sleep(1)
        writer.stop()
        t.join()
        fake_run.assert_called_once()
        expected_calls = [mock.call(vcl_writer.UNITS_LOCKER),
                          mock.call(vcl_writer.BINDS_LOCKER)]
        self.assertEqual(expected_calls,
                         writer.locker.init.call_args_list)

    def test_stop(self):
        manager = mock.Mock(storage=mock.Mock())
        writer = vcl_writer.VCLWriter(manager)
        writer.running = True
        writer.stop()
        self.assertFalse(writer.running)

    def test_run(self):
        manager = mock.Mock(storage=mock.Mock())
        writer = vcl_writer.VCLWriter(manager)
        writer.run_units = mock.Mock()
        writer.run_binds = mock.Mock()
        writer.run()
        writer.run_units.assert_called_once()
        writer.run_binds.assert_called_once()

    def test_run_units(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802")]
        strg = mock.Mock()
        strg.retrieve_units.return_value = units
        manager = mock.Mock(storage=strg)
        writer = vcl_writer.VCLWriter(manager, max_items=3)
        writer._is_unit_up = lambda unit: unit == units[1]
        writer.bind_units = mock.Mock()
        writer.locker = mock.Mock()
        writer.run_units()
        writer.locker.lock.assert_called_with(vcl_writer.UNITS_LOCKER)
        strg.retrieve_units.assert_called_with(state="creating", limit=3)
        writer.locker.unlock.assert_called_with(vcl_writer.UNITS_LOCKER)
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
        strg.retrieve_units.return_value = units
        strg.retrieve_binds.return_value = [storage.Bind("myapp.cloud.tsuru.io",
                                                         instance1)]
        manager = mock.Mock(storage=strg)
        writer = vcl_writer.VCLWriter(manager, max_items=3)
        writer.bind_units(units)
        expected_calls = [mock.call(instance_name="myinstance", state="created"),
                          mock.call(instance_name="yourinstance", state="created")]
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
        manager = mock.Mock(storage=mock.Mock())
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

    def test_run_binds(self):
        units = [storage.Unit(id="i-0800", dns_name="unit1.cloud.tsuru.io",
                              secret="abc123", state="started"),
                 storage.Unit(id="i-8001", dns_name="unit2.cloud.tsuru.io",
                              secret="abc321", state="started")]
        instance1 = storage.Instance(name="wat", units=units)
        instance2 = storage.Instance(name="wet", units=units)
        binds = [storage.Bind(instance=instance1, app_host="cool", state="creating"),
                 storage.Bind(instance=instance2, app_host="bool", state="creating")]
        strg = mock.Mock()
        strg.retrieve_units.return_value = units
        strg.retrieve_binds.return_value = binds
        manager = mock.Mock(storage=strg)
        writer = vcl_writer.VCLWriter(manager, max_items=3)
        writer.locker = mock.Mock()
        writer.run_binds()
        writer.locker.lock.assert_called_with(vcl_writer.BINDS_LOCKER)
        writer.locker.unlock.assert_called_with(vcl_writer.BINDS_LOCKER)
        strg.retrieve_units.assert_called_once_with(state="started",
                                                    instance_name={"$in": ["wat", "wet"]})
        strg.retrieve_binds.assert_called_once_with(state="creating", limit=3)
        expected_write_vcl_calls = [mock.call("unit1.cloud.tsuru.io", "abc123", "cool"),
                                    mock.call("unit2.cloud.tsuru.io", "abc321", "cool"),
                                    mock.call("unit1.cloud.tsuru.io", "abc123", "bool"),
                                    mock.call("unit2.cloud.tsuru.io", "abc321", "bool")]
        self.assertEqual(expected_write_vcl_calls, manager.write_vcl.call_args_list)
        expected_update_bind_calls = [mock.call(binds[0], state="created"),
                                      mock.call(binds[1], state="created")]
        self.assertEqual(expected_update_bind_calls, strg.update_bind.call_args_list)
