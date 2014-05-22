# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import threading
import time
import unittest

import mock

from feaas import storage
from feaas.runners import instance_terminator


class InstanceTerminatorTestCase(unittest.TestCase):

    def test_init(self):
        strg = storage.MongoDBStorage()
        manager = mock.Mock(storage=strg)
        terminator = instance_terminator.InstanceTerminator(manager, interval=3)
        self.assertEqual(manager, terminator.manager)
        self.assertEqual(strg, terminator.storage)
        self.assertEqual(3, terminator.interval)
        self.assertEqual(strg.db, terminator.locker.db)

    def test_loop_and_stop(self):
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        fake_run = mock.Mock()
        terminator = instance_terminator.InstanceTerminator(manager, interval=3)
        terminator.run = fake_run
        t = threading.Thread(target=terminator.loop)
        t.start()
        time.sleep(1)
        terminator.stop()
        t.join()
        fake_run.assert_called_once()
        self.assertFalse(terminator.running)

    def test_run(self):
        instance = storage.Instance(name="something")
        manager = mock.Mock(storage=mock.Mock())
        get_instance = mock.Mock()
        get_instance.return_value = instance
        terminator = instance_terminator.InstanceTerminator(manager, interval=3)
        terminator.get_instance = get_instance
        terminator.terminate_instance = mock.Mock()
        terminator.run()
        terminator.get_instance.assert_called_once()
        terminator.terminate_instance.assert_called_with(instance)

    def test_run_instance_not_found(self):
        manager = mock.Mock(storage=mock.Mock())
        terminator = instance_terminator.InstanceTerminator(manager, interval=3)
        terminator.get_instance = mock.Mock(side_effect=storage.InstanceNotFoundError())
        terminator.terminate_instance = mock.Mock()
        terminator.run()
        terminator.terminate_instance.assert_not_called()

    def test_get_instance(self):
        instance = storage.Instance(name="something")
        strg = mock.Mock()
        strg.retrieve_instance.return_value = instance
        manager = mock.Mock(storage=strg)
        terminator = instance_terminator.InstanceTerminator(manager, interval=3)
        terminator.locker = mock.Mock()
        got_instance = terminator.get_instance()
        self.assertEqual(instance, got_instance)
        self.assertEqual("terminating", got_instance.state)
        strg.retrieve_instance.assert_called_with(state="removed")
        strg.store_instance.assert_called_with(instance)
        terminator.locker.lock.assert_called_with(terminator.lock_name)
        terminator.locker.unlock.assert_called_with(terminator.lock_name)

    def test_get_instance_not_found(self):
        strg = mock.Mock()
        strg.retrieve_instance.side_effect = storage.InstanceNotFoundError()
        manager = mock.Mock(storage=strg)
        terminator = instance_terminator.InstanceTerminator(manager, interval=3)
        terminator.locker = mock.Mock()
        with self.assertRaises(storage.InstanceNotFoundError):
            terminator.get_instance()
        terminator.locker.lock.assert_called_with(terminator.lock_name)
        terminator.locker.unlock.assert_called_with(terminator.lock_name)

    def test_terminate_instance(self):
        instance = storage.Instance(name="something")
        strg = mock.Mock()
        manager = mock.Mock(storage=strg)
        terminator = instance_terminator.InstanceTerminator(manager, interval=3)
        terminator.locker = mock.Mock()
        terminator.terminate_instance(instance)
        terminator.locker.lock.assert_called_with(terminator.lock_name)
        manager.terminate_instance.assert_called_with(instance.name)
        terminator.locker.unlock.assert_called_with(terminator.lock_name)
        strg.remove_instance.assert_called_with(instance.name)
