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

    def __init__(self, app_host, instance, created_at=None,
                 state="creating"):
        self.app_host = app_host
        self.instance = instance
        self.state = state
        self.created_at = created_at or datetime.datetime.utcnow()

    def to_dict(self):
        return {"app_host": self.app_host, "instance_name": self.instance.name,
                "created_at": self.created_at, "state": self.state}


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

    def retrieve_instance(self, name):
        instance = self.db[self.collection_name].find_one({"name": name})
        if not instance:
            raise InstanceNotFoundError()
        del instance["_id"]
        return Instance(name=instance["name"],
                        units=self.retrieve_units(instance_name=name))

    def retrieve_units(self, limit=None, **query):
        cursor = self.db.units.find(query)
        if limit:
            cursor = cursor.limit(limit)
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

    def init_locker(self, lock_name):
        try:
            self.db.vcl_lock.insert({"_id": lock_name, "state": 0})
        except pymongo.errors.DuplicateKeyError:
            pass

    def lock(self, lock_name):
        n = 0
        while n < 1:
            r = self.db.vcl_lock.update({"_id": lock_name, "state": 0},
                                        {"_id": lock_name, "state": 1})
            n = r["n"]

    def unlock(self, lock_name):
        r = self.db.vcl_lock.update({"_id": lock_name, "state": 1},
                                    {"_id": lock_name, "state": 0})
        if r["n"] < 1:
            raise DoubleUnlockError(lock_name)

    def update_units(self, units, **changes):
        ids = [u.id for u in units]
        self.db.units.update({"id": {"$in": ids}}, {"$set": changes},
                             multi=True)
