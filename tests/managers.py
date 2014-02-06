# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

from varnishapi import storage


class FakeInstance(object):

    def __init__(self, name):
        self.name = name
        self.bound = []

    def bind(self, app_host):
        self.bound.append(app_host)

    def unbind(self, app_host):
        self.bound.remove(app_host)


class FakeManager(object):

    def __init__(self, storage=None):
        self.instances = []

    def add_instance(self, name):
        self.instances.append(FakeInstance(name))

    def bind(self, name, app_host):
        pass

    def unbind(self, name, app_host):
        pass

    def remove_instance(self, name):
        index = -1
        for i, instance in enumerate(self.instances):
            if instance.name == name:
                index = i
                break
        if index > -1:
            del self.instances[index]
        else:
            raise storage.InstanceNotFoundError()

    def info(self, name):
        pass

    def is_ok(self, name):
        for instance in self.instances:
            if instance.name == name:
                return True, ""
        return False, ""

    def reset(self):
        self.instances = []
