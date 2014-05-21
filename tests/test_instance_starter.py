# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import threading
import time
import unittest

import mock

from feaas import storage
from feaas.runners import instance_starter


class InstanceStarterTestCase(unittest.TestCase):

    def test_init(self):
        strg = storage.MongoDBStorage()
        manager = mock.Mock(storage=strg)
        starter = instance_starter.InstanceStarter(manager, interval=3)
        self.assertEqual(manager, starter.manager)
        self.assertEqual(strg, starter.storage)
        self.assertEqual(3, starter.interval)
        self.assertEqual(strg.db, starter.locker.db)

    def test_loop_and_stop(self):
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        fake_run = mock.Mock()
        starter = instance_starter.InstanceStarter(manager, interval=3)
        starter.run = fake_run
        t = threading.Thread(target=starter.loop)
        t.start()
        time.sleep(1)
        starter.stop()
        t.join()
        fake_run.assert_called_once()
        self.assertFalse(starter.running)

    def test_run(self):
        instance = storage.Instance(name="something")
        manager = mock.Mock(storage=mock.Mock())
        get_instance = mock.Mock()
        get_instance.return_value = instance
        starter = instance_starter.InstanceStarter(manager, interval=3)
        starter.get_instance = get_instance
        starter.start_instance = mock.Mock()
        starter.run()
        starter.get_instance.assert_called_once()
        starter.start_instance.assert_called_with(instance)

    def test_run_instance_not_found(self):
        manager = mock.Mock(storage=mock.Mock())
        starter = instance_starter.InstanceStarter(manager, interval=3)
        starter.get_instance = mock.Mock(side_effect=storage.InstanceNotFoundError())
        starter.start_instance = mock.Mock()
        starter.run()
        starter.start_instance.assert_not_called()

    def test_get_instance(self):
        instance = storage.Instance(name="something")
        strg = mock.Mock()
        strg.retrieve_instance.return_value = instance
        manager = mock.Mock(storage=strg)
        starter = instance_starter.InstanceStarter(manager, interval=3)
        starter.locker = mock.Mock()
        got_instance = starter.get_instance()
        self.assertEqual(instance, got_instance)
        self.assertEqual("starting", got_instance.state)
        strg.retrieve_instance.assert_called_with(state="creating")
        strg.store_instance.assert_called_with(instance)
        starter.locker.lock.assert_called_with(starter.lock_name)
        starter.locker.unlock.assert_called_with(starter.lock_name)

    def test_get_instance_not_found(self):
        strg = mock.Mock()
        strg.retrieve_instance.side_effect = storage.InstanceNotFoundError()
        manager = mock.Mock(storage=strg)
        starter = instance_starter.InstanceStarter(manager, interval=3)
        starter.locker = mock.Mock()
        with self.assertRaises(storage.InstanceNotFoundError):
            starter.get_instance()
        starter.locker.lock.assert_called_with(starter.lock_name)
        starter.locker.unlock.assert_called_with(starter.lock_name)

    def test_start_instance(self):
        instance = storage.Instance(name="something")
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        starter = instance_starter.InstanceStarter(manager, interval=3)
        starter.locker = mock.Mock()
        starter.start_instance(instance)
        self.assertEqual("created", instance.state)
        starter.locker.lock.assert_called_with(starter.lock_name)
        manager.start_instance.assert_called_with(instance.name)
        starter.locker.unlock.assert_called_with(starter.lock_name)
        strg.store_instance.assert_called_with(instance)

    def test_start_instance_error(self):
        instance = storage.Instance(name="something")
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        manager.start_instance.side_effect = ValueError("something went wrong")
        starter = instance_starter.InstanceStarter(manager, interval=3)
        starter.locker = mock.Mock()
        starter.start_instance(instance)
        self.assertEqual("error", instance.state)
        starter.locker.lock.assert_called_with(starter.lock_name)
        starter.locker.unlock.assert_called_with(starter.lock_name)
        strg.store_instance.assert_called_with(instance)
