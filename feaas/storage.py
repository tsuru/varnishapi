# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import datetime

import pymongo


class InstanceNotFoundError(Exception):
    pass


class InstanceAlreadyExistsError(Exception):
    pass


class DoubleUnlockError(Exception):
    pass


class Instance(object):

    def __init__(self, name=None, units=None):
        self.name = name
        self.units = units or []
        for unit in self.units:
            unit.instance = self

    def to_dict(self):
        return {"name": self.name}

    def add_unit(self, unit):
        self.units.append(unit)

    def remove_unit(self, unit):
        self.units.remove(unit)


class Unit(object):

    def __init__(self, id=None, dns_name=None, secret=None, state="creating",
                 instance=None):
        self.id = id
        self.dns_name = dns_name
        self.secret = secret
        self.state = state
        self.instance = instance

    def to_dict(self):
        return {"id": self.id, "dns_name": self.dns_name,
                "secret": self.secret, "state": self.state,
                "instance_name": self.instance.name}


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
        self.db[self.collection_name].update({"name": instance.name}, instance.to_dict(),
                                             upsert=True)
        self.db.units.remove({"instance_name": instance.name})
        if instance.units:
            self.db.units.insert([u.to_dict() for u in instance.units])

    def retrieve_instance(self, name, fetch_units=False):
        instance = self.db[self.collection_name].find_one({"name": name})
        if not instance:
            raise InstanceNotFoundError()
        del instance["_id"]
        units = None
        if fetch_units:
            units = self.retrieve_units(name)
        return Instance(name=instance["name"], units=units)

    def retrieve_units(self, instance_name):
        cursor = self.db.units.find({"instance_name": instance_name})
        units = []
        for unit in cursor:
            unit["instance"] = Instance(name=unit["instance_name"])
            del unit["instance_name"]
            del unit["_id"]
            units.append(Unit(**unit))
        return units

    def remove_instance(self, name):
        self.db.binds.remove({"instance_name": name})
        self.db.units.remove({"instance_name": name})
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

    def lock_vcl_writer(self):
        n = 0
        while n < 1:
            r = self.db.vcl_lock.update({"_id": "1", "state": 0},
                                        {"_id": "1", "state": 1},
                                        upsert=True)
            n = r["n"]

    def unlock_vcl_writer(self):
        r = self.db.vcl_lock.update({"_id": "1", "state": 1},
                                    {"$set": {"state": 0}})
        if r["n"] < 1:
            raise DoubleUnlockError()

    def load_units(self, state, limit=None):
        cursor = self.db.units.find({"state": state})
        if limit:
            cursor = cursor.limit(limit)
        units = []
        for unit in cursor:
            unit["instance"] = Instance(name=unit["instance_name"])
            del unit["instance_name"]
            del unit["_id"]
            units.append(Unit(**unit))
        return units

    def update_units(self, units, **changes):
        ids = [u.id for u in units]
        self.db.units.update({"id": {"$in": ids}}, {"$set": changes},
                             multi=True)
