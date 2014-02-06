# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

from varnishapi import storage


class FakeInstance(object):

    def __init__(self, name, state):
        self.name = name
        self.state = state
        self.bound = []

    def bind(self, app_host):
        self.bound.append(app_host)

    def unbind(self, app_host):
        self.bound.remove(app_host)


class FakeManager(object):

    def __init__(self, storage=None):
        self.instances = []

    def add_instance(self, name, state="running"):
        self.instances.append(FakeInstance(name, state))

    def bind(self, name, app_host):
        index, instance = self.find_instance(name)
        if index < 0:
            raise storage.InstanceNotFoundError()
        instance.bind(app_host)

    def unbind(self, name, app_host):
        index, instance = self.find_instance(name)
        if index < 0:
            raise storage.InstanceNotFoundError()
        instance.unbind(app_host)

    def remove_instance(self, name):
        index, _ = self.find_instance(name)
        if index > -1:
            del self.instances[index]
        else:
            raise storage.InstanceNotFoundError()

    def info(self, name):
        index, instance = self.find_instance(name)
        if index < 0:
            raise storage.InstanceNotFoundError()
        return {"name": instance.name}

    def status(self, name):
        index, instance = self.find_instance(name)
        if index < 0:
            raise storage.InstanceNotFoundError()
        return instance.state

    def find_instance(self, name):
        for i, instance in enumerate(self.instances):
            if instance.name == name:
                return i, instance
        return -1, None

    def reset(self):
        self.instances = []
