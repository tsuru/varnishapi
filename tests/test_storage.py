# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import unittest

import freezegun
import pymongo

from feaas import storage


class InstanceTestCase(unittest.TestCase):

    def test_init_units(self):
        instance = storage.Instance()
        self.assertEqual([], instance.units)
        units = [storage.Unit(dns_name="instance.cloud.tsuru.io", id="i-0800",
                              secret="abc123")]
        instance = storage.Instance(units=units)
        self.assertEqual(units, instance.units)

    def test_to_dict(self):
        units = [storage.Unit(dns_name="instance.cloud.tsuru.io", id="i-0800",
                              secret="abc123")]
        instance = storage.Instance(name="myinstance", units=units)
        expected = {"name": "myinstance",
                    "units": [u.to_dict() for u in instance.units]}
        self.assertEqual(expected, instance.to_dict())

    def test_add_unit(self):
        unit1 = storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800")
        unit2 = storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801")
        instance = storage.Instance()
        instance.add_unit(unit1)
        instance.add_unit(unit2)
        self.assertEqual([unit1, unit2], instance.units)

    def test_remove_unit(self):
        unit1 = storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800")
        unit2 = storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801")
        instance = storage.Instance()
        instance.add_unit(unit1)
        instance.add_unit(unit2)
        self.assertEqual([unit1, unit2], instance.units)
        instance.remove_unit(unit1)
        self.assertEqual([unit2], instance.units)


class UnitTestCase(unittest.TestCase):

    def test_to_dict(self):
        unit = storage.Unit(id="i-0800", dns_name="instance.cloud.tsuru.io",
                            secret="abc123")
        expected = {"id": "i-0800", "dns_name": "instance.cloud.tsuru.io",
                    "secret": "abc123"}
        self.assertEqual(expected, unit.to_dict())


class BindTestCase(unittest.TestCase):

    def test_to_dict(self):
        instance = storage.Instance(name="myinstance")
        bind = storage.Bind("wat.g1.cloud.tsuru.io", instance)
        expected = {"app_host": "wat.g1.cloud.tsuru.io",
                    "instance_name": "myinstance",
                    "created_at": bind.created_at}
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

    def test_store_instance(self):
        instance = storage.Instance(name="secret",
                                    units=[storage.Unit(id="i-0800",
                                                        dns_name="secret.pos.com")])
        self.storage.store_instance(instance)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": "secret"})
        instance = self.client.feaas_test.instances.find_one({"name": "secret"})
        expected = {"name": "secret", "_id": instance["_id"],
                    "units": [{"id": "i-0800", "secret": None, "dns_name": "secret.pos.com"}]}
        self.assertEqual(expected, instance)

    def test_store_instance_with_units(self):
        units = [storage.Unit(dns_name="instance.cloud.tsuru.io", id="i-0800")]
        instance = storage.Instance(name="secret", units=units)
        self.storage.store_instance(instance)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": "secret"})
        instance = self.client.feaas_test.instances.find_one({"name": "secret"})
        expected = {"name": "secret", "_id": instance["_id"],
                    "units": [u.to_dict() for u in units]}
        self.assertEqual(expected, instance)

    def test_store_instance_update(self):
        units = [storage.Unit(dns_name="instance.cloud.tsuru.io", id="i-0800")]
        instance = storage.Instance(name="secret", units=units)
        self.storage.store_instance(instance)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": "secret"})
        unit = storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801")
        units.append(unit)
        instance.add_unit(unit)
        self.storage.store_instance(instance)
        instance = self.client.feaas_test.instances.find_one({"name": "secret"})
        expected = {"name": "secret", "_id": instance["_id"],
                    "units": [u.to_dict() for u in units]}
        self.assertEqual(expected, instance)

    def test_retrieve_instance(self):
        units = [storage.Unit(dns_name="instance.cloud.tsuru.io", id="i-0800")]
        expected = storage.Instance(name="what", units=units)
        self.storage.store_instance(expected)
        got = self.storage.retrieve_instance("what")
        self.assertEqual(expected.to_dict(), got.to_dict())

    def test_retrieve_instance_not_found(self):
        with self.assertRaises(storage.InstanceNotFoundError):
            self.storage.retrieve_instance("secret")

    def test_remove_instance(self):
        instance = storage.Instance(name="years")
        self.storage.store_instance(instance)
        self.storage.remove_instance(instance.name)
        self.assertIsNone(self.client.feaas_test.instances.find_one({"name": instance.name}))

    @freezegun.freeze_time("2014-02-16 12:00:01")
    def test_store_bind(self):
        instance = storage.Instance(name="years")
        bind = storage.Bind(app_host="something.where.com", instance=instance)
        self.storage.store_bind(bind)
        self.addCleanup(self.client.feaas_test.binds.remove,
                        {"instance_name": "years"})
        got = self.client.feaas_test.binds.find_one({"instance_name": "years"})
        expected = bind.to_dict()
        expected["_id"] = got["_id"]
        expected["created_at"] = got["created_at"]
        self.assertEqual(expected, got)

    @freezegun.freeze_time("2014-02-16 12:00:01")
    def test_retrieve_binds(self):
        instance = storage.Instance(name="years")
        bind1 = storage.Bind(app_host="something.where.com", instance=instance)
        self.storage.store_bind(bind1)
        bind2 = storage.Bind(app_host="belong.where.com", instance=instance)
        self.storage.store_bind(bind2)
        self.addCleanup(self.client.feaas_test.binds.remove,
                        {"instance_name": "years"})
        binds = self.storage.retrieve_binds("years")
        binds = [b.to_dict() for b in binds]
        self.assertEqual([bind1.to_dict(), bind2.to_dict()], binds)

    def test_remove_bind(self):
        instance = storage.Instance(name="years")
        bind = storage.Bind(app_host="something.where.com", instance=instance)
        self.storage.store_bind(bind)
        self.addCleanup(self.client.feaas_test.binds.remove,
                        {"instance_name": "years"})
        self.storage.remove_bind(bind)
        self.assertEqual([], self.storage.retrieve_binds("years"))
