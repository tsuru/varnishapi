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

    def __init__(self, name=None, state="creating", units=None):
        self.name = name
        self.state = state
        self.units = units or []
        for unit in self.units:
            unit.instance = self

    def to_dict(self):
        return {"name": self.name, "state": self.state}

    def add_unit(self, unit):
        unit.instance = self
        self.units.append(unit)

    def remove_unit(self, unit):
        unit.instance = self
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

    def store_instance(self, instance, save_units=True):
        self.db[self.collection_name].update({"name": instance.name}, instance.to_dict(),
                                             upsert=True)
        if save_units:
            self.db.units.remove({"instance_name": instance.name})
            if instance.units:
                self.db.units.insert([u.to_dict() for u in instance.units])

    def retrieve_instance(self, check_liveness=False, **query):
        if check_liveness:
            query["state"] = {"$nin": ["removed", "terminating"]}
        instance = self.db[self.collection_name].find_one(query)
        if not instance:
            raise InstanceNotFoundError()
        del instance["_id"]
        instance["units"] = self.retrieve_units(instance_name=instance["name"])
        return Instance(**instance)

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

    def store_scale_job(self, job):
        if "state" not in job:
            job["state"] = "pending"
        self.db.scale_jobs.insert(job)

    def get_scale_job(self):
        job = self.db.scale_jobs.find_one({"state": "pending"})
        if not job:
            return
        job["state"] = "processing"
        self.db.scale_jobs.update({"_id": job["_id"]},
                                  {"$set": {"state": job["state"]}})
        return job

    def reset_scale_job(self, job):
        if "_id" not in job:
            raise ValueError("job is not persisted")
        job["state"] = "pending"
        self.db.scale_jobs.update({"_id": job["_id"]},
                                  {"$set": {"state": job["state"]}})

    def finish_scale_job(self, job):
        if "_id" not in job:
            raise ValueError("job is not persisted")
        job["state"] = "done"
        self.db.scale_jobs.update({"_id": job["_id"]},
                                  {"$set": {"state": job["state"]}})

    def store_bind(self, bind):
        self.db.binds.insert(bind.to_dict())

    def retrieve_binds(self, limit=None, **query):
        binds = []
        cursor = self.db.binds.find(query)
        if limit:
            cursor = cursor.limit(limit)
        for item in cursor:
            instance = Instance(name=item["instance_name"])
            binds.append(Bind(app_host=item["app_host"],
                              instance=instance,
                              created_at=item["created_at"],
                              state=item["state"]))
        return binds

    def remove_bind(self, bind):
        self.db.binds.remove({"app_host": bind.app_host,
                              "instance_name": bind.instance.name})

    def update_units(self, units, **changes):
        ids = [u.id for u in units]
        self.db.units.update({"id": {"$in": ids}}, {"$set": changes},
                             multi=True)

    def update_bind(self, bind, **changes):
        self.db.binds.update(bind.to_dict(), {"$set": changes}, multi=True)


class MultiLocker(object):

    def __init__(self, storage):
        self.db = storage.db

    def init(self, lock_name):
        try:
            self.db.multi_locker.insert({"_id": lock_name, "state": 0})
        except pymongo.errors.DuplicateKeyError:
            pass

    def destroy(self, lock_name):
        self.db.multi_locker.remove({"_id": lock_name})

    def lock(self, lock_name):
        n = 0
        while n < 1:
            r = self.db.multi_locker.update({"_id": lock_name, "state": 0},
                                            {"_id": lock_name, "state": 1})
            n = r["n"]

    def unlock(self, lock_name):
        r = self.db.multi_locker.update({"_id": lock_name, "state": 1},
                                        {"_id": lock_name, "state": 0})
        if r["n"] < 1:
            raise DoubleUnlockError(lock_name)
