# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import json
import unittest

import pymongo

from varnishapi import storage


class InstanceTestCase(unittest.TestCase):

    def test_to_dict(self):
        instance = storage.Instance(name="myinstance",
                                    dns_name="instance.cloud.tsuru.io",
                                    id="i-0800")
        expected = {"id": "i-0800", "dns_name": "instance.cloud.tsuru.io",
                    "name": "myinstance"}
        self.assertEqual(expected, instance.to_dict())

    def test_to_json(self):
        instance = storage.Instance(name="myinstance",
                                    dns_name="instance.cloud.tsuru.io",
                                    id="i-0800")
        json_str = instance.to_json()
        expected = {"id": "i-0800", "dns_name": "instance.cloud.tsuru.io",
                    "name": "myinstance"}
        self.assertEqual(expected, json.loads(json_str))


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
        self.storage.store(instance)
        instance = self.client.feaas_test.instances.find_one({"name": "secret"})
        expected = {"id": "i-0800", "name": "secret",
                    "dns_name": "secret.pos.com", "_id": instance["_id"]}
        self.assertEqual(expected, instance)

    def test_retrieve(self):
        expected = storage.Instance(id="i-0800", name="what",
                                    dns_name="secret.pos.com")
        self.storage.store(expected)
        got = self.storage.retrieve("what")
        self.assertEqual(expected.to_dict(), got.to_dict())

    def test_retrieve_not_found(self):
        with self.assertRaises(ValueError) as cm:
            self.storage.retrieve("secret")
        exc = cm.exception
        self.assertEqual(("Instance not found",),
                         exc.args)

    def test_remove(self):
        instance = storage.Instance(id="i-0800", name="years",
                                    dns_name="secret.pos.com")
        self.storage.store(instance)
        self.storage.remove(instance.name)
        self.assertIsNone(self.client.feaas_test.instances.find_one({"name": instance.name}))
