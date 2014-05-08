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
        writer = vcl_writer.VCLWriter(strg, interval=10, max_items=3)
        self.assertEqual(strg, writer.storage)
        self.assertEqual(10, writer.interval)
        self.assertEqual(3, writer.max_items)

    def test_loop(self):
        fake_run = mock.Mock()
        writer = vcl_writer.VCLWriter(None, interval=3, max_items=3)
        writer.run = fake_run
        t = threading.Thread(target=writer.loop)
        t.start()
        time.sleep(1)
        writer.stop()
        t.join()
        fake_run.assert_called()

    def test_stop(self):
        writer = vcl_writer.VCLWriter(None)
        writer.running = True
        writer.stop()
        self.assertFalse(writer.running)

    def test_run(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802")]
        strg = mock.Mock()
        strg.load_units.return_value = units
        writer = vcl_writer.VCLWriter(strg, max_items=3)
        writer._is_unit_up = lambda unit: unit == units[1]
        writer.run()
        strg.lock_vcl_writer.assert_called_once()
        strg.load_units.assert_called_with("creating", limit=3)
        strg.unlock_vcl_writer.assert_called_once()

    @mock.patch("telnetlib.Telnet")
    def test_is_unit_up_up(self, Telnet):
        telnet_client = mock.Mock()
        Telnet.return_value = telnet_client
        unit = storage.Unit(dns_name="instance1.cloud.tsuru.io")
        writer = vcl_writer.VCLWriter(None, max_items=3)
        self.assertTrue(writer._is_unit_up(unit))
        Telnet.assert_called_with(unit.dns_name, "6082", timeout=3)
        telnet_client.close.assert_called_once()

    @mock.patch("telnetlib.Telnet")
    def test_is_unit_up_down(self, Telnet):
        Telnet.side_effect = ValueError()
        unit = storage.Unit(dns_name="instance1.cloud.tsuru.io")
        writer = vcl_writer.VCLWriter(None, max_items=3)
        self.assertFalse(writer._is_unit_up(unit))
        Telnet.assert_called_with(unit.dns_name, "6082", timeout=3)
