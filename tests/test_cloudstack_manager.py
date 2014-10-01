# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os
import unittest

from feaas.managers import cloudstack


class CloudStackManagerTestCase(unittest.TestCase):

    def set_envs(self, url="http://cloudstackapi", api_key="key",
                 secret_key="secret"):
        os.environ["CLOUDSTACK_API_URL"] = self.url = url
        os.environ["CLOUDSTACK_API_KEY"] = self.api_key = api_key
        os.environ["CLOUDSTACK_SECRET_KEY"] = self.secret_key = secret_key

    def del_envs(self):
        del os.environ["CLOUDSTACK_API_URL"], os.environ["CLOUDSTACK_API_KEY"], \
            os.environ["CLOUDSTACK_SECRET_KEY"]

    def test_init(self):
        self.set_envs()
        self.addCleanup(self.del_envs)
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
        self.set_envs()
        self.addCleanup(self.del_envs)
        exc = cm.exception
        self.assertEqual(("env var CLOUDSTACK_API_KEY is required",),
                         exc.args)

    def test_init_no_secret_key(self):
        os.environ["CLOUDSTACK_API_URL"] = "something"
        os.environ["CLOUDSTACK_API_KEY"] = "not_secret"
        with self.assertRaises(cloudstack.MissConfigurationError) as cm:
            cloudstack.CloudStackManager(storage=None)
        self.set_envs()
        self.addCleanup(self.del_envs)
        exc = cm.exception
        self.assertEqual(("env var CLOUDSTACK_SECRET_KEY is required",),
                         exc.args)
