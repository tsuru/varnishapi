# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import unittest

import pymongo

from feaas import storage


class InstanceTestCase(unittest.TestCase):

    def test_to_dict(self):
        instance = storage.Instance(name="myinstance",
                                    dns_name="instance.cloud.tsuru.io",
                                    id="i-0800")
        expected = {"id": "i-0800", "dns_name": "instance.cloud.tsuru.io",
                    "name": "myinstance", "secret": None}
        self.assertEqual(expected, instance.to_dict())


class BindTestCase(unittest.TestCase):

    def test_to_dict(self):
        instance = storage.Instance(name="myinstance",
                                    dns_name="instance.cloud.tsuru.io",
                                    id="i-0800")
        bind = storage.Bind("wat.g1.cloud.tsuru.io", instance)
        expected = {"app_host": "wat.g1.cloud.tsuru.io",
                    "instance_name": "myinstance"}
        self.assertEqual(expected, bind.to_dict())


class MongoDBStorageTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = pymongo.MongoClient('localhost', 27017)

    @classmethod
    def tearDownClass(cls):
        cls.client.drop_database("feaas_test")

    def setUp(self):
        self.storage = storage.MongoDBStorage(dbname="feaas_test")

    def test_store(self):
        instance = storage.Instance(id="i-0800", name="secret",
                                    dns_name="secret.pos.com")
        self.storage.store_instance(instance)
        instance = self.client.feaas_test.instances.find_one({"name": "secret"})
        expected = {"id": "i-0800", "name": "secret",
                    "dns_name": "secret.pos.com", "_id": instance["_id"],
                    "secret": None}
        self.assertEqual(expected, instance)

    def test_retrieve(self):
        expected = storage.Instance(id="i-0800", name="what",
                                    dns_name="secret.pos.com")
        self.storage.store_instance(expected)
        got = self.storage.retrieve_instance("what")
        self.assertEqual(expected.to_dict(), got.to_dict())

    def test_retrieve_not_found(self):
        with self.assertRaises(storage.InstanceNotFoundError):
            self.storage.retrieve_instance("secret")

    def test_remove(self):
        instance = storage.Instance(id="i-0800", name="years",
                                    dns_name="secret.pos.com")
        self.storage.store_instance(instance)
        self.storage.remove_instance(instance.name)
        self.assertIsNone(self.client.feaas_test.instances.find_one({"name": instance.name}))
