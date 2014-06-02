# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

from feaas import runners, storage


class InstanceScalator(runners.Base):
    lock_name = "instance_scalator"

    def __init__(self, *args, **kwargs):
        super(InstanceScalator, self).__init__(*args, **kwargs)
        self.init_locker(self.lock_name)

    def run(self):
        try:
            instance, job = self.get_job()
            if not job:
                return
            self.scale_instance(instance, job["quantity"])
            self.storage.finish_scale_job(job)
        except storage.InstanceNotFoundError:
            pass

    def get_job(self):
        self.locker.lock(self.lock_name)
        try:
            job = self.storage.get_scale_job()
            if not job:
                return None, None
            instance = self.storage.retrieve_instance(name=job["instance"],
                                                      check_liveness=True)
            if instance.state != "started":
                return None, None
            instance.state = "scaling"
            self.storage.store_instance(instance)
            return instance, job
        except storage.InstanceNotFoundError:
            self.storage.finish_scale_job(job)
            raise
        finally:
            self.locker.unlock(self.lock_name)

    def scale_instance(self, instance, quantity):
        lock_name = "%s/%s" % (self.lock_name, instance.name)
        self.locker.init(lock_name)
        self.locker.lock(lock_name)
        try:
            try:
                self.manager.physical_scale(instance, quantity)
            finally:
                instance.state = "started"
                self.storage.store_instance(instance, save_units=False)
        finally:
            self.locker.unlock(lock_name)
