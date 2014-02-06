# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import json
import os
import unittest

from mock import patch
from collections import namedtuple

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
