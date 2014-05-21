# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import time


class Base(object):

    def __init__(self, manager, interval):
        self.manager = manager
        self.storage = manager.storage
        self.interval = interval

    def loop(self):
        self.running = True
        while self.running:
            self.run()
            time.sleep(self.interval)

    def stop(self):
        self.running = False
