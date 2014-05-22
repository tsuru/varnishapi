# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import time

from feaas import storage


class Base(object):

    def __init__(self, manager, interval, *locks):
        self.manager = manager
        self.storage = manager.storage
        self.interval = interval

    def init_locker(self, *lock_names):
        self.locker = storage.MultiLocker(self.storage)
        for lock_name in lock_names:
            self.locker.init(lock_name)

    def loop(self):
        self.running = True
        while self.running:
            self.run()
            time.sleep(self.interval)

    def stop(self):
        self.running = False
