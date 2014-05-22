# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import telnetlib
import threading

from feaas import runners

UNITS_LOCKER = "units"
BINDS_LOCKER = "binds"


class VCLWriter(runners.Base):
    """
    VCLWriter provides a method that keeps it running forever doing two things:

        - whenever a new unit is added to an instance, bind this unit to all
          applications that are already bound to this unit
        - whenever a new bind is made, connect all started units to the
          application that is being created
    """

    def __init__(self, manager, interval=10, max_items=None):
        super(VCLWriter, self).__init__(manager, interval)
        self.init_locker(UNITS_LOCKER, BINDS_LOCKER)
        self.max_items = max_items

    def run(self):
        t1 = threading.Thread(target=self.run_units)
        t1.start()
        t2 = threading.Thread(target=self.run_binds)
        t2.start()
        t1.join()
        t2.join()

    def run_units(self):
        self.locker.lock(UNITS_LOCKER)
        try:
            units = self.storage.retrieve_units(state="creating", limit=self.max_items)
            up_units = []
            for unit in units:
                if self._is_unit_up(unit):
                    up_units.append(unit)
            if up_units:
                self.bind_units(up_units)
                self.storage.update_units(up_units, state="started")
        finally:
            self.locker.unlock(UNITS_LOCKER)

    def bind_units(self, units):
        binds_dict = {}
        for unit in units:
            iname = unit.instance.name
            if iname not in binds_dict:
                binds_dict[iname] = self.storage.retrieve_binds(instance_name=iname,
                                                                state="created")
            binds = binds_dict[iname]
            for bind in binds:
                self.manager.write_vcl(unit.dns_name, unit.secret, bind.app_host)

    def _is_unit_up(self, unit):
        try:
            client = telnetlib.Telnet(unit.dns_name, "6082", timeout=3)
            client.close()
            return True
        except:
            return False

    def run_binds(self):
        self.locker.lock(BINDS_LOCKER)
        try:
            binds = self.storage.retrieve_binds(state="creating", limit=self.max_items)
            instance_names = [b.instance.name for b in binds]
            units = self.storage.retrieve_units(state="started",
                                                instance_name={"$in": instance_names})
            for bind in binds:
                for unit in units:
                    self.manager.write_vcl(unit.dns_name, unit.secret, bind.app_host)
                self.storage.update_bind(bind, state="created")
        finally:
            self.locker.unlock(BINDS_LOCKER)
