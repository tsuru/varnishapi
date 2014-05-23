# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import unittest

import freezegun
import pymongo

from feaas import storage


class InstanceTestCase(unittest.TestCase):

    def test_init_with_units(self):
        units = [storage.Unit(id="i-0800"), storage.Unit(id="i-0801")]
        instance = storage.Instance(name="something", units=units)
        for unit in units:
            self.assertEqual(instance, unit.instance)

    def test_to_dict(self):
        instance = storage.Instance(name="myinstance", state="created")
        expected = {"name": "myinstance", "state": "created"}
        self.assertEqual(expected, instance.to_dict())

    def test_add_unit(self):
        unit1 = storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800")
        unit2 = storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801")
        instance = storage.Instance()
        instance.add_unit(unit1)
        instance.add_unit(unit2)
        self.assertEqual([unit1, unit2], instance.units)
        self.assertEqual(instance, unit1.instance)
        self.assertEqual(instance, unit2.instance)

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
        instance = storage.Instance(name="myinstance")
        unit = storage.Unit(id="i-0800", dns_name="instance.cloud.tsuru.io",
                            secret="abc123", state="started", instance=instance)
        expected = {"id": "i-0800", "dns_name": "instance.cloud.tsuru.io",
                    "secret": "abc123", "state": "started",
                    "instance_name": "myinstance"}
        self.assertEqual(expected, unit.to_dict())


class BindTestCase(unittest.TestCase):

    def test_to_dict(self):
        instance = storage.Instance(name="myinstance")
        bind = storage.Bind("wat.g1.cloud.tsuru.io", instance)
        expected = {"app_host": "wat.g1.cloud.tsuru.io",
                    "instance_name": "myinstance",
                    "created_at": bind.created_at,
                    "state": bind.state}
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
        instance = storage.Instance(name="secret")
        self.storage.store_instance(instance)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": "secret"})
        instance = self.client.feaas_test.instances.find_one({"name": "secret"})
        expected = {"name": "secret", "_id": instance["_id"], "state": "creating"}
        self.assertEqual(expected, instance)

    def test_store_instance_with_units(self):
        units = [storage.Unit(dns_name="instance.cloud.tsuru.io", id="i-0800")]
        instance = storage.Instance(name="secret", units=units)
        self.storage.store_instance(instance)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": "secret"})
        self.addCleanup(self.client.feaas_test.units.remove, {"instance_name": "secret"})
        instance = self.client.feaas_test.instances.find_one({"name": "secret"})
        expected = {"name": "secret", "_id": instance["_id"], "state": "creating"}
        self.assertEqual(expected, instance)
        unit = self.client.feaas_test.units.find_one({"id": "i-0800",
                                                      "instance_name": "secret"})
        expected = units[0].to_dict()
        expected["_id"] = unit["_id"]
        self.assertEqual(expected, unit)

    def test_store_instance_update_with_units(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802")]
        instance = storage.Instance(name="secret", units=units)
        self.storage.store_instance(instance)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": "secret"})
        self.addCleanup(self.client.feaas_test.units.remove, {"instance_name": "secret"})
        self.assert_units(units, "secret")
        new_units = units[1:]
        instance.units = new_units
        self.storage.store_instance(instance)
        self.assert_units(new_units, "secret")

    def test_store_instance_update_without_units(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802")]
        instance = storage.Instance(name="secret", units=units)
        self.storage.store_instance(instance)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": "secret"})
        self.addCleanup(self.client.feaas_test.units.remove, {"instance_name": "secret"})
        instance.units = []
        instance.state = "started"
        self.storage.store_instance(instance, save_units=False)
        self.assert_units(units, instance.name)
        got_instance = self.storage.retrieve_instance(name=instance.name)
        self.assertEqual("started", got_instance.state)

    def test_retrieve_instance(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802")]
        instance = storage.Instance(name="what", units=units)
        self.storage.store_instance(instance)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": instance.name})
        self.addCleanup(self.client.feaas_test.units.remove, {"instance_name": instance.name})
        got_instance = self.storage.retrieve_instance(name="what")
        self.assertEqual([u.to_dict() for u in units],
                         [u.to_dict() for u in got_instance.units])
        self.assertEqual(instance.to_dict(), got_instance.to_dict())

    def test_retrieve_instance_check_liveness(self):
        instance = storage.Instance(name="what", state="removed")
        self.storage.store_instance(instance)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": instance.name})
        with self.assertRaises(storage.InstanceNotFoundError):
            self.storage.retrieve_instance(name="what", check_liveness=True)

    def test_retrieve_instance_not_found(self):
        with self.assertRaises(storage.InstanceNotFoundError):
            self.storage.retrieve_instance(name="secret")

    def test_retrieve_instance_by_state(self):
        instance1 = storage.Instance(name="where", state="creating")
        self.storage.store_instance(instance1)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": instance1.name})
        instance2 = storage.Instance(name="when", state="creating")
        self.storage.store_instance(instance2)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": instance2.name})
        instance3 = storage.Instance(name="who", state="starting")
        self.storage.store_instance(instance3)
        self.addCleanup(self.client.feaas_test.instances.remove, {"name": instance3.name})
        instance = self.storage.retrieve_instance(state="creating")
        self.assertEqual(instance1.name, instance.name)
        self.assertEqual(instance1.state, instance.state)

    def test_remove_instance(self):
        instance = storage.Instance(name="years")
        self.storage.store_instance(instance)
        self.storage.remove_instance(instance.name)
        self.assertIsNone(self.client.feaas_test.instances.find_one({"name": instance.name}))

    def test_remove_instance_with_units(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802")]
        instance = storage.Instance(name="secret", units=units)
        self.storage.store_instance(instance)
        self.storage.remove_instance(instance.name)
        self.assertIsNone(self.client.feaas_test.units.find_one({"instance_name": instance.name}))

    def test_remove_instance_with_binds(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802")]
        instance = storage.Instance(name="secret", units=units)
        self.storage.store_instance(instance)
        bind = storage.Bind("myapp.cloud.tsuru.io", instance)
        self.storage.store_bind(bind)
        self.storage.remove_instance(instance.name)
        self.assertIsNone(self.client.feaas_test.binds.find_one({"instance_name": instance.name}))

    def test_store_scale_job(self):
        job = {"instance": "myapp", "quantity": 2, "state": "done"}
        self.storage.store_scale_job(job)
        self.addCleanup(self.client.feaas_test.scale_jobs.remove, {"instance": "myapp"})
        got_job = self.client.feaas_test.scale_jobs.find_one()
        self.assertEqual(job, got_job)

    def test_store_scale_job_no_state(self):
        job = {"instance": "myapp", "quantity": 2}
        self.storage.store_scale_job(job)
        self.addCleanup(self.client.feaas_test.scale_jobs.remove, {"instance": "myapp"})
        self.assertEqual("pending", job["state"])
        got_job = self.client.feaas_test.scale_jobs.find_one()
        self.assertEqual(job, got_job)

    def test_get_scale_job(self):
        job1 = {"instance": "myapp", "quantity": 2}
        self.storage.store_scale_job(job1)
        job2 = {"instance": "myapp", "quantity": 3}
        self.storage.store_scale_job(job2)
        self.addCleanup(self.client.feaas_test.scale_jobs.remove, {"instance": "myapp"})
        got_job = self.storage.get_scale_job()
        expected_job = self.client.feaas_test.scale_jobs.find_one()
        self.assertEqual(expected_job, got_job)
        self.assertEqual("processing", got_job["state"])

    def test_get_scale_job_not_found(self):
        job = self.storage.get_scale_job()
        self.assertIsNone(job)

    def test_get_scale_job_no_pending_job(self):
        job1 = {"instance": "myapp", "quantity": 2, "state": "processing"}
        self.storage.store_scale_job(job1)
        job2 = {"instance": "myapp", "quantity": 2, "state": "done"}
        self.storage.store_scale_job(job2)
        self.addCleanup(self.client.feaas_test.scale_jobs.remove, {"instance": "myapp"})
        job = self.storage.get_scale_job()
        self.assertIsNone(job)

    def test_finish_scale_job(self):
        job = {"instance": "myapp", "quantity": 2, "state": "processing"}
        self.storage.store_scale_job(job)
        self.addCleanup(self.client.feaas_test.scale_jobs.remove, {"instance": "myapp"})
        self.storage.finish_scale_job(job)
        self.assertEqual("done", job["state"])
        persisted_job = self.client.feaas_test.scale_jobs.find_one()
        self.assertEqual(job, persisted_job)

    def test_finish_scale_job_no_id(self):
        job = {"instance": "myapp", "quantity": 2, "state": "processing"}
        with self.assertRaises(ValueError) as cm:
            self.storage.finish_scale_job(job)
        exc = cm.exception
        self.assertEqual(("job is not persisted",), exc.args)

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
        binds = self.storage.retrieve_binds(instance_name="years")
        binds = [b.to_dict() for b in binds]
        self.assertEqual([bind1.to_dict(), bind2.to_dict()], binds)

    @freezegun.freeze_time("2014-02-16 12:00:01")
    def test_retrieve_binds_limit(self):
        instance = storage.Instance(name="years")
        bind1 = storage.Bind(app_host="something.where.com", instance=instance)
        self.storage.store_bind(bind1)
        bind2 = storage.Bind(app_host="belong.where.com", instance=instance)
        self.storage.store_bind(bind2)
        self.addCleanup(self.client.feaas_test.binds.remove,
                        {"instance_name": "years"})
        binds = self.storage.retrieve_binds(instance_name="years", limit=1)
        binds = [b.to_dict() for b in binds]
        self.assertEqual([bind1.to_dict()], binds)

    @freezegun.freeze_time("2014-02-16 12:00:01")
    def test_retrieve_binds_query(self):
        instance = storage.Instance(name="years")
        bind1 = storage.Bind(app_host="something.where.com", instance=instance)
        self.storage.store_bind(bind1)
        bind2 = storage.Bind(app_host="belong.where.com", instance=instance)
        self.storage.store_bind(bind2)
        self.addCleanup(self.client.feaas_test.binds.remove,
                        {"instance_name": "years"})
        binds = self.storage.retrieve_binds(app_host="belong.where.com")
        binds = [b.to_dict() for b in binds]
        self.assertEqual([bind2.to_dict()], binds)

    def test_remove_bind(self):
        instance = storage.Instance(name="years")
        bind = storage.Bind(app_host="something.where.com", instance=instance)
        self.storage.store_bind(bind)
        self.addCleanup(self.client.feaas_test.binds.remove,
                        {"instance_name": "years"})
        self.storage.remove_bind(bind)
        self.assertEqual([], self.storage.retrieve_binds(instance_name="years"))

    def test_retrieve_units(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802",
                              state="started")]
        instance = storage.Instance(name="great", units=units)
        self.storage.store_instance(instance)
        self.addCleanup(self.storage.remove_instance, instance.name)
        got_units = self.storage.retrieve_units(state="creating")
        self.assertEqual([u.to_dict() for u in units[:2]],
                         [u.to_dict() for u in got_units])

    def test_retrieve_units_limited(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802",
                              state="started")]
        instance = storage.Instance(name="great", units=units)
        self.storage.store_instance(instance)
        self.addCleanup(self.storage.remove_instance, instance.name)
        got_units = self.storage.retrieve_units(state="creating", limit=1)
        self.assertEqual([u.to_dict() for u in units[:1]],
                         [u.to_dict() for u in got_units])

    def test_update_units(self):
        units = [storage.Unit(dns_name="instance1.cloud.tsuru.io", id="i-0800"),
                 storage.Unit(dns_name="instance2.cloud.tsuru.io", id="i-0801"),
                 storage.Unit(dns_name="instance3.cloud.tsuru.io", id="i-0802",
                              state="started")]
        instance = storage.Instance(name="great", units=units)
        self.storage.store_instance(instance)
        self.addCleanup(self.storage.remove_instance, instance.name)
        units[0].state = "started"
        units[1].state = "started"
        self.storage.update_units(units, state="started")
        got_units = self.storage.retrieve_units(state="started")
        self.assertEqual([u.to_dict() for u in units],
                         [u.to_dict() for u in got_units])

    def test_update_bind(self):
        instance = storage.Instance(name="great")
        bind = storage.Bind("wat.g1.cloud.tsuru.io", instance)
        self.storage.store_bind(bind)
        self.addCleanup(self.storage.remove_bind, bind)
        self.storage.update_bind(bind, state="created")
        bind = self.storage.retrieve_binds(instance_name="great")[0]
        self.assertEqual("created", bind.state)

    def assert_units(self, expected_units, instance_name):
        cursor = self.client.feaas_test.units.find({"instance_name": instance_name})
        units = []
        expected = [u.to_dict() for u in expected_units]
        for i, unit in enumerate(cursor):
            expected[i]["_id"] = unit["_id"]
            units.append(unit)
        self.assertEqual(expected, units)
