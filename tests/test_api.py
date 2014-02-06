# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import json
import unittest

from varnishapi import api
from . import managers


class APITestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.manager = managers.FakeManager()
        cls.old_get_manager = api.get_manager
        api.get_manager = lambda: cls.manager
        cls.api = api.api.test_client()

    def setUp(self):
        self.manager.reset()

    def test_create_instance(self):
        resp = self.api.post("/resources", data={"name": "someapp"})
        self.assertEqual(201, resp.status_code)
        self.assertEqual("someapp", self.manager.instances[0].name)

    def test_create_instance_without_name(self):
        resp = self.api.post("/resources", data={"names": "someapp"})
        self.assertEqual(400, resp.status_code)
        self.assertEqual("name is required", resp.data)
        self.assertEqual([], self.manager.instances)

    def test_remove_instance(self):
        self.manager.add_instance("someapp")
        resp = self.api.delete("/resources/someapp")
        self.assertEqual(200, resp.status_code)
        self.assertEqual("", resp.data)
        self.assertEqual([], self.manager.instances)

    def test_remove_instance_not_found(self):
        resp = self.api.delete("/resources/someapp")
        self.assertEqual(404, resp.status_code)
        self.assertEqual("Instance not found", resp.data)
        self.assertEqual([], self.manager.instances)

    def test_bind(self):
        self.manager.add_instance("someapp")
        resp = self.api.post("/resources/someapp",
                             data={"app-host": "someapp.cloud.tsuru.io"})
        self.assertEqual(201, resp.status_code)
        self.assertEqual("null", resp.data)
        bind = self.manager.instances[0].bound[0]
        self.assertEqual("someapp.cloud.tsuru.io", bind)

    def test_bind_without_app_host(self):
        resp = self.api.post("/resources/someapp",
                             data={"app_hooost": "someapp.cloud.tsuru.io"})
        self.assertEqual(400, resp.status_code)
        self.assertEqual("app-host is required", resp.data)

    def test_bind_instance_not_found(self):
        resp = self.api.post("/resources/someapp",
                             data={"app-host": "someapp.cloud.tsuru.io"})
        self.assertEqual(404, resp.status_code)
        self.assertEqual("Instance not found", resp.data)

    def test_unbind(self):
        self.manager.add_instance("someapp")
        self.manager.bind("someapp", "someapp.cloud.tsuru.io")
        resp = self.api.delete("/resources/someapp/hostname/someapp.cloud.tsuru.io")
        self.assertEqual(200, resp.status_code)
        self.assertEqual("", resp.data)
        self.assertEqual([], self.manager.instances[0].bound)

    def test_unbind_instance_not_found(self):
        resp = self.api.delete("/resources/someapp/hostname/someapp.cloud.tsuru.io")
        self.assertEqual(404, resp.status_code)
        self.assertEqual("Instance not found", resp.data)

    def test_info(self):
        self.manager.add_instance("someapp")
        resp = self.api.get("/resources/someapp")
        self.assertEqual(200, resp.status_code)
        data = json.loads(resp.data)
        self.assertEqual({"name": "someapp"}, data)

    def test_info_instance_not_found(self):
        resp = self.api.get("/resources/someapp")
        self.assertEqual(404, resp.status_code)
        self.assertEqual("Instance not found", resp.data)
