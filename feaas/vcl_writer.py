# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import telnetlib
import time

UNITS_LOCKER = "units"
BINDS_LOCKER = "binds"


class VCLWriter(object):

    def __init__(self, manager, interval=10, max_items=None):
        self.manager = manager
        self.storage = manager.storage
        self.interval = interval
        self.max_items = max_items

    def loop(self):
        self.running = True
        self.storage.init_locker(UNITS_LOCKER)
        self.storage.init_locker(BINDS_LOCKER)
        while self.running:
            self.run()
            time.sleep(self.interval)

    def stop(self):
        self.running = False

    def run(self):
        self.storage.lock(UNITS_LOCKER)
        try:
            units = self.storage.load_units("creating", limit=self.max_items)
            up_units = []
            for unit in units:
                if self._is_unit_up(unit):
                    up_units.append(unit)
            if up_units:
                self.bind_units(up_units)
                self.storage.update_units(up_units, state="started")
        finally:
            self.storage.unlock(UNITS_LOCKER)

    def bind_units(self, units):
        binds_dict = {}
        for unit in units:
            instance_name = unit.instance.name
            if instance_name not in binds_dict:
                binds_dict[instance_name] = self.storage.retrieve_binds(instance_name)
            binds = binds_dict[instance_name]
            for bind in binds:
                self.manager.write_vcl(unit.dns_name, unit.secret, bind.app_host)

    def _is_unit_up(self, unit):
        try:
            client = telnetlib.Telnet(unit.dns_name, "6082", timeout=3)
            client.close()
            return True
        except:
            return False
