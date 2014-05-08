# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import telnetlib
import time


class VCLWriter(object):

    def __init__(self, storage, interval=10, max_items=None):
        self.storage = storage
        self.interval = interval
        self.max_items = max_items

    def loop(self):
        self.running = True
        while self.running:
            self.run()
            time.sleep(self.interval)

    def stop(self):
        self.running = False

    def run(self):
        self.storage.lock_vcl_writer()
        try:
            units = self.storage.load_units("creating", limit=self.max_items)
            up_units = []
            for unit in units:
                if self._is_unit_up(unit):
                    up_units.append(unit)
            if up_units:
                self.storage.update_units(up_units, state="started")
        finally:
            self.storage.unlock_vcl_writer()

    def _is_unit_up(self, unit):
        try:
            client = telnetlib.Telnet(unit.dns_name, "6082", timeout=3)
            client.close()
            return True
        except:
            return False
