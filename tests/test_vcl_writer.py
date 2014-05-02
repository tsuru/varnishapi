# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import unittest

from feaas import vcl_writer


class VCLWriterTestCase(unittest.TestCase):

    def test_init(self):
        writer = vcl_writer.VCLWriter(interval=10, max_items=3)
        self.assertEqual(10, writer.interval)
        self.assertEqual(3, writer.max_items)
