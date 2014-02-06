# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import json
import unittest

from varnishapi import storage


class InstanceTestCase(unittest.TestCase):

    def test_to_json(self):
        instance = storage.Instance(name="myinstance",
                                    dns_name="instance.cloud.tsuru.io",
                                    id="i-0800")
        json_str = instance.to_json()
        expected = {"id": "i-0800", "dns_name": "instance.cloud.tsuru.io",
                    "name": "myinstance"}
        self.assertEqual(expected, json.loads(json_str))
