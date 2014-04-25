# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import pymongo


class InstanceNotFoundError(Exception):
    pass


class InstanceAlreadyExistsError(Exception):
    pass


class Instance(object):

    def __init__(self, name=None, dns_name=None, id=None, secret=None):
        self.name = name
        self.dns_name = dns_name
        self.id = id
        self.secret = secret

    def to_dict(self):
        return {"name": self.name, "dns_name": self.dns_name,
                "id": self.id, "secret": self.secret}


class Bind(object):

    def __init__(self, app_host, instance):
        self.app_host = app_host
        self.instance = instance

    def to_dict(self):
        return {"app_host": self.app_host, "instance_name": self.instance.name}


class MongoDBStorage(object):

    def __init__(self, mongo_uri=None, dbname=None):
        self.mongo_uri = mongo_uri or "mongodb://localhost:27017/"
        self.dbname = dbname or "feaas"
        client = pymongo.MongoClient(self.mongo_uri)
        self.db = client[self.dbname]
        self.collection_name = "instances"

    def store(self, instance):
        self.db[self.collection_name].insert(instance.to_dict())

    def retrieve(self, name):
        instance = self.db[self.collection_name].find_one({"name": name})
        if not instance:
            raise InstanceNotFoundError()
        del instance["_id"]
        return Instance(**instance)

    def remove(self, name):
        self.db[self.collection_name].remove({"name": name})

    def retrieve_public_key(self):
        return self.key["public_body"]

    def retrieve_private_key(self):
        return self.key["private_body"]

    @property
    def key(self):
        return self.db.keys.find_one()
