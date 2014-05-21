# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

from feaas import runners, storage


class InstanceStarter(runners.Base):
    lock_name = "instance_starter"

    def __init__(self, manager, interval=10):
        super(InstanceStarter, self).__init__(manager, interval)
        self.locker = storage.MultiLocker(self.storage)
        self.locker.init(self.lock_name)

    def run(self):
        try:
            instance = self.get_instance()
            self.start_instance(instance)
        except storage.InstanceNotFoundError:
            pass

    def get_instance(self):
        self.locker.lock(self.lock_name)
        try:
            instance = self.storage.retrieve_instance(state="creating")
            instance.state = "starting"
            self.storage.store_instance(instance)
            return instance
        finally:
            self.locker.unlock(self.lock_name)

    def start_instance(self, instance):
        self.locker.lock(self.lock_name)
        try:
            try:
                self.manager.start_instance(instance.name)
                instance.state = "created"
            except:
                instance.state = "error"
            self.storage.store_instance(instance)
        finally:
            self.locker.unlock(self.lock_name)