# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import datetime

import pymongo


class InstanceNotFoundError(Exception):
    pass


class InstanceAlreadyExistsError(Exception):
    pass


class Instance(object):

    def __init__(self, name=None, dns_name=None, id=None, secret=None, units=None):
        self.name = name
        self.dns_name = dns_name
        self.id = id
        self.secret = secret
        self.units = units or []

    def to_dict(self):
        return {"name": self.name, "dns_name": self.dns_name,
                "id": self.id, "secret": self.secret,
                "units": [u.to_dict() for u in self.units]}

    def add_unit(self, unit):
        self.units.append(unit)

    def remove_unit(self, unit):
        self.units.remove(unit)


class Unit(object):

    def __init__(self, id=None, dns_name=None, secret=None):
        self.id = id
        self.dns_name = dns_name
        self.secret = secret

    def to_dict(self):
        return {"id": self.id, "dns_name": self.dns_name,
                "secret": self.secret}


class Bind(object):

    def __init__(self, app_host, instance, created_at=None):
        self.app_host = app_host
        self.instance = instance
        self.created_at = created_at or datetime.datetime.utcnow()

    def to_dict(self):
        return {"app_host": self.app_host, "instance_name": self.instance.name,
                "created_at": self.created_at}


class MongoDBStorage(object):

    def __init__(self, mongo_uri=None, dbname=None):
        self.mongo_uri = mongo_uri or "mongodb://localhost:27017/"
        self.dbname = dbname or "feaas"
        client = pymongo.MongoClient(self.mongo_uri)
        self.db = client[self.dbname]
        self.collection_name = "instances"

    def store_instance(self, instance):
        self.db[self.collection_name].insert(instance.to_dict())

    def retrieve_instance(self, name):
        instance = self.db[self.collection_name].find_one({"name": name})
        if not instance:
            raise InstanceNotFoundError()
        del instance["_id"]
        instance["units"] = [Unit(**u) for u in instance["units"]]
        return Instance(**instance)

    def remove_instance(self, name):
        self.db[self.collection_name].remove({"name": name})

    def store_bind(self, bind):
        self.db.binds.insert(bind.to_dict())

    def retrieve_binds(self, instance_name):
        binds = []
        items = self.db.binds.find({"instance_name": instance_name})
        for item in items:
            instance = Instance(name=item["instance_name"])
            binds.append(Bind(app_host=item["app_host"],
                              instance=instance,
                              created_at=item["created_at"]))
        return binds

    def remove_bind(self, bind):
        self.db.binds.remove({"app_host": bind.app_host,
                              "instance_name": bind.instance.name})
