# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import unittest

import mock

from feaas import plugin


class CommandNotFoundErrorTestCase(unittest.TestCase):

    def test_init(self):
        error = plugin.CommandNotFoundError("scale")
        self.assertEqual(("scale",), error.args)
        self.assertEqual("scale", error.name)

    def test_str(self):
        error = plugin.CommandNotFoundError("scale")
        self.assertEqual('command "scale" not found', str(error))

    def test_unicode(self):
        error = plugin.CommandNotFoundError("scale")
        self.assertEqual(u'command "scale" not found', unicode(error))


class TsuruPluginTestCase(unittest.TestCase):

    def setUp(self):
        plugin.API_URL = "http://something.cloud.tsuru.io"

    @mock.patch("urllib.urlopen")
    @mock.patch("sys.stdout")
    def test_scale(self, stdout, urlopen):
        result = mock.Mock()
        result.getcode.return_value = 200
        urlopen.return_value = result
        plugin.scale(["-i", "myinstance", "-n", "10"])
        urlopen.assert_called_with(plugin.API_URL + "/resources/myinstance/scale",
                                   data="quantity=10")
        stdout.write.assert_called_with("Instance successfully scaled to 10 units\n")

    @mock.patch("urllib.urlopen")
    @mock.patch("sys.stderr")
    def test_scale_failure(self, stderr, urlopen):
        result = mock.Mock()
        result.getcode.return_value = 400
        result.read.return_value = "Invalid quantity"
        urlopen.return_value = result
        with self.assertRaises(SystemExit) as cm:
            plugin.scale(["-i", "myinstance", "-n", "10"])
        exc = cm.exception
        self.assertEqual(1, exc.code)
        urlopen.assert_called_with(plugin.API_URL + "/resources/myinstance/scale",
                                   data="quantity=10")
        stderr.write.assert_called_with("ERROR: Invalid quantity\n")

    @mock.patch("sys.stderr")
    def test_scale_missing_instance(self, stderr):
        with self.assertRaises(SystemExit) as cm:
            plugin.scale(["-n", "1"])
        exc = cm.exception
        self.assertEqual(2, exc.code)
        expected_msg = "usage: scale [-h] [-i INSTANCE] [-n QUANTITY]\n"
        stderr.write.assert_called_with(expected_msg)

    @mock.patch("sys.stderr")
    def test_scale_missing_quantity(self, stderr):
        with self.assertRaises(SystemExit) as cm:
            plugin.scale(["-i", "abc"])
        exc = cm.exception
        self.assertEqual(2, exc.code)
        expected_msg = "usage: scale [-h] [-i INSTANCE] [-n QUANTITY]\n"
        stderr.write.assert_called_with(expected_msg)

    @mock.patch("sys.stderr")
    def test_scale_invalid_quantity(self, stderr):
        with self.assertRaises(SystemExit) as cm:
            plugin.scale(["-i", "abc", "-n", "0"])
        exc = cm.exception
        self.assertEqual(2, exc.code)
        expected_msg = "quantity must be a positive integer\n"
        stderr.write.assert_called_with(expected_msg)

    def test_get_url(self):
        plugin.API_URL = "http://localhost:5353"
        url = plugin.get_url("/something")
        self.assertEqual("http://localhost:5353/something", url)

    def test_get_url_trailing_slash(self):
        plugin.API_URL = "http://localhost:5353/"
        url = plugin.get_url("/something")
        self.assertEqual("http://localhost:5353/something", url)

    def test_get_url_multiple_trailing_slashes(self):
        plugin.API_URL = "http://some.cloud.tsuru.io///"
        url = plugin.get_url("/thing")
        self.assertEqual("http://some.cloud.tsuru.io/thing", url)

    def test_get_url_no_leading_slash_in_path(self):
        plugin.API_URL = "http://some.cloud.tsuru.io///"
        url = plugin.get_url("thing")
        self.assertEqual("http://some.cloud.tsuru.io/thing", url)

    def test_get_command(self):
        cmd = plugin.get_command("scale")
        self.assertEqual(plugin.scale, cmd)

    def test_get_command_not_found(self):
        with self.assertRaises(plugin.CommandNotFoundError) as cm:
            plugin.get_command("something i don't know")
        exc = cm.exception
        self.assertEqual("something i don't know", exc.name)

    def test_main(self):
        original_scale = plugin.scale

        def clean():
            plugin.scale = original_scale
        self.addCleanup(clean)
        plugin.scale = mock.Mock()
        args = ["hello", "world"]
        plugin.main("scale", args)
        plugin.scale.assert_called_with(args)

    @mock.patch("sys.stderr")
    def test_main_command_not_found(self, stderr):
        args = ["hello", "world"]
        with self.assertRaises(SystemExit) as cm:
            plugin.main("wat", args)
        exc = cm.exception
        self.assertEqual(2, exc.code)
        stderr.write.assert_called_with(u'command "wat" not found\n')
