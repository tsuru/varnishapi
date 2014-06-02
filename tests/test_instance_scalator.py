# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import unittest

import mock

from feaas import runners, storage
from feaas.runners import instance_scalator


class InstanceScalatorTestCase(unittest.TestCase):

    def test_init(self):
        strg = storage.MongoDBStorage()
        manager = mock.Mock(storage=strg)
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        self.assertEqual(manager, scalator.manager)
        self.assertEqual(strg, scalator.storage)
        self.assertEqual(3, scalator.interval)
        self.assertEqual(strg.db, scalator.locker.db)
        scalator.locker.lock(scalator.lock_name)
        scalator.locker.unlock(scalator.lock_name)

    def test_inherits_from_base_runner(self):
        manager = mock.Mock(storage=mock.Mock())
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        self.assertIsInstance(scalator, runners.Base)

    def test_run(self):
        job, instance = ({"instance": "something", "quantity": 2},
                         storage.Instance(name="something"))
        get_job = mock.Mock()
        get_job.return_value = instance, job
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        scalator.get_job = get_job
        scalator.scale_instance = mock.Mock()
        scalator.run()
        get_job.assert_called_once()
        scalator.scale_instance.assert_called_with(instance, 2)
        strg.finish_scale_job.assert_called_with(job)

    def test_run_no_job(self):
        get_job = mock.Mock()
        get_job.return_value = None, None
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        scalator.get_job = get_job
        scalator.scale_instance = mock.Mock()
        scalator.run()
        scalator.scale_instance.assert_not_called()

    def test_run_instance_not_found(self):
        get_job = mock.Mock()
        get_job.side_effect = storage.InstanceNotFoundError()
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        scalator.get_job = get_job
        scalator.scale_instance = mock.Mock()
        scalator.run()
        scalator.scale_instance.assert_not_called()

    def test_get_job(self):
        instance = storage.Instance(name="something", state="started")
        job = {"instance": "something", "quantity": 3}
        strg = mock.Mock()
        strg.get_scale_job.return_value = job
        strg.retrieve_instance.return_value = instance
        manager = mock.Mock(storage=strg)
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        scalator.locker = mock.Mock()
        got_instance, got_job = scalator.get_job()
        self.assertEqual("scaling", got_instance.state)
        self.assertEqual(instance, got_instance)
        self.assertEqual(job, got_job)
        scalator.locker.lock.assert_called_with(scalator.lock_name)
        strg.get_scale_job.assert_called_once()
        strg.retrieve_instance.assert_called_with(name="something",
                                                  check_liveness=True)
        strg.store_instance.assert_called_with(got_instance)
        scalator.locker.unlock.assert_called_with(scalator.lock_name)

    def test_get_job_instance_not_started(self):
        instance = storage.Instance(name="something", state="scaling")
        job = {"instance": "something", "quantity": 3}
        strg = mock.Mock()
        strg.get_scale_job.return_value = job
        strg.retrieve_instance.return_value = instance
        manager = mock.Mock(storage=strg)
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        scalator.locker = mock.Mock()
        got_instance, got_job = scalator.get_job()
        self.assertIsNone(got_instance)
        self.assertIsNone(got_job)
        scalator.locker.lock.assert_called_with(scalator.lock_name)
        strg.retrieve_instance.assert_called_with(name="something",
                                                  check_liveness=True)
        scalator.locker.unlock.assert_called_with(scalator.lock_name)

    def test_get_job_instance_not_found(self):
        job = {"instance": "something", "quantity": 3}
        strg = mock.Mock()
        strg.get_scale_job.return_value = job
        strg.retrieve_instance.side_effect = storage.InstanceNotFoundError()
        manager = mock.Mock(storage=strg)
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        scalator.locker = mock.Mock()
        with self.assertRaises(storage.InstanceNotFoundError):
            scalator.get_job()
        scalator.locker.lock.assert_called_with(scalator.lock_name)
        strg.finish_scale_job.assert_called_with(job)
        scalator.locker.unlock.assert_called_with(scalator.lock_name)

    def test_get_job_no_job(self):
        strg = mock.Mock()
        strg.get_scale_job.return_value = None
        manager = mock.Mock(storage=strg)
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        scalator.locker = mock.Mock()
        got_instance, got_job = scalator.get_job()
        self.assertIsNone(got_instance)
        self.assertIsNone(got_job)
        scalator.locker.lock.assert_called_with(scalator.lock_name)
        scalator.locker.unlock.assert_called_with(scalator.lock_name)

    def test_scale_instance(self):
        instance = storage.Instance(name="something", state="started")
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        scalator.locker = mock.Mock()
        scalator.scale_instance(instance, 2)
        self.assertEqual("started", instance.state)
        lock_name = "%s/something" % scalator.lock_name
        scalator.locker.init.assert_called_with(lock_name)
        scalator.locker.lock.assert_called_with(lock_name)
        manager.physical_scale.assert_called_with(instance, 2)
        strg.store_instance.assert_called_with(instance, save_units=False)
        scalator.locker.unlock.assert_called_with(lock_name)

    def test_scale_always_unlock_and_change_state(self):
        instance = storage.Instance(name="something", state="started")
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        manager.physical_scale.side_effect = ValueError("something happened")
        scalator = instance_scalator.InstanceScalator(manager, interval=3)
        scalator.locker = mock.Mock()
        with self.assertRaises(ValueError) as cm:
            scalator.scale_instance(instance, 2)
        exc = cm.exception
        self.assertEqual(("something happened",), exc.args)
        self.assertEqual("started", instance.state)
        lock_name = "%s/something" % scalator.lock_name
        scalator.locker.init.assert_called_with(lock_name)
        scalator.locker.lock.assert_called_with(lock_name)
        strg.store_instance.assert_called_with(instance, save_units=False)
        scalator.locker.unlock.assert_called_with(lock_name)
