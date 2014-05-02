# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.


class VCLWriter(object):

    def __init__(self, interval=10, max_items=None):
        self.interval = interval
        self.max_items = max_items

    def loop(self):
        pass
