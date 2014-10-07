# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

from feaas import runners, storage


class InstanceTerminator(runners.Base):
    lock_name = "instance_terminator"

    def __init__(self, *args, **kwargs):
        super(InstanceTerminator, self).__init__(*args, **kwargs)
        self.init_locker(self.lock_name)

    def run(self):
        try:
            instance = self.get_instance()
            self.terminate_instance(instance)
        except storage.InstanceNotFoundError:
            pass

    def get_instance(self):
        self.locker.lock(self.lock_name)
        try:
            instance = self.storage.retrieve_instance(state="removed")
            instance.state = "terminating"
            self.storage.store_instance(instance)
            return instance
        finally:
            self.locker.unlock(self.lock_name)

    def terminate_instance(self, instance):
        self.locker.lock(self.lock_name)
        try:
            self.manager.terminate_instance(instance.name)
        finally:
            try:
                self.storage.remove_instance(instance.name)
            finally:
                self.locker.unlock(self.lock_name)
