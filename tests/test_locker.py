# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import threading
import time
import unittest

import pymongo

from feaas import storage


class MultiLockerTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = pymongo.MongoClient('localhost', 27017)

    @classmethod
    def tearDownClass(cls):
        cls.client.drop_database("feaas_test")

    def setUp(self):
        strg = storage.MongoDBStorage(dbname="feaas_test")
        self.locker = storage.MultiLocker(strg)

    def test_init_locker(self):
        self.locker.init_locker("test_init")
        self.addCleanup(self.client.feaas_test.vcl_lock.remove, {"_id": "test_init"})
        lock = self.client.feaas_test.vcl_lock.find_one()
        self.assertEqual("test_init", lock["_id"])
        self.assertEqual(0, lock["state"])

    def test_init_locker_duplicate(self):
        self.locker.init_locker("test_init")
        self.addCleanup(self.client.feaas_test.vcl_lock.remove, {"_id": "test_init"})
        self.locker.lock("test_init")
        self.locker.init_locker("test_init")
        lock = self.client.feaas_test.vcl_lock.find_one()
        self.assertEqual("test_init", lock["_id"])
        self.assertEqual(1, lock["state"])

    def test_lock(self):
        self.locker.init_locker("test_lock")
        self.addCleanup(self.client.feaas_test.vcl_lock.remove, {"_id": "test_lock"})
        self.locker.lock("test_lock")
        lock = self.client.feaas_test.vcl_lock.find_one()
        self.assertEqual("test_lock", lock["_id"])
        self.assertEqual(1, lock["state"])
        self.locker.unlock("test_lock")
        self.locker.lock("test_lock")
        lock = self.client.feaas_test.vcl_lock.find_one()
        self.assertEqual("test_lock", lock["_id"])
        self.assertEqual(1, lock["state"])

    def test_double_lock(self):
        self.locker.init_locker("test_lock")
        self.addCleanup(self.client.feaas_test.vcl_lock.remove, {"_id": "test_lock"})
        self.locker.lock("test_lock")
        t = threading.Thread(target=self.locker.lock, args=("test_lock",))
        t.start()
        time.sleep(.1)
        self.locker.unlock("test_lock")
        t.join()
        lock = self.client.feaas_test.vcl_lock.find_one()
        self.assertEqual("test_lock", lock["_id"])
        self.assertEqual(1, lock["state"])

    def test_unlock(self):
        self.locker.init_locker("test_unlock")
        self.addCleanup(self.client.feaas_test.vcl_lock.remove, {"_id": "test_unlock"})
        self.locker.lock("test_unlock")
        self.locker.unlock("test_unlock")
        lock = self.client.feaas_test.vcl_lock.find_one()
        self.assertEqual("test_unlock", lock["_id"])
        self.assertEqual(0, lock["state"])

    def test_double_unlock(self):
        self.locker.init_locker("test_unlock")
        self.addCleanup(self.client.feaas_test.vcl_lock.remove, {"_id": "test_unlock"})
        self.locker.lock("test_unlock")
        self.locker.unlock("test_unlock")
        with self.assertRaises(storage.DoubleUnlockError):
            self.locker.unlock("test_unlock")
