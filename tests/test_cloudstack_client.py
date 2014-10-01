# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import base64
import unittest

from feaas.managers import cloudstack_client


class CloudStackClientTestCase(unittest.TestCase):

    def test_encode_user_data(self):
        client = cloudstack_client.CloudStack("http://localhost", "api_key",
                                              "secret!")
        expected = base64.b64encode("some user data")
        self.assertEqual(expected, client.encode_user_data("some user data"))
