# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os
import unittest

from mock import Mock, patch

from feaas import storage as api_storage
from feaas.managers import ec2


class EC2ManagerTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["EC2_ACCESS_KEY"] = cls.access_key = "access"
        os.environ["EC2_SECRET_KEY"] = cls.secret_key = "secret"
        os.environ["AMI_ID"] = cls.ami_id = "ami-123"
        os.environ["SUBNET_ID"] = cls.subnet_id = "subnet-123"

    def setUp(self):
        os.environ["EC2_ENDPOINT"] = "http://amazonaws.com"

    @patch("boto.ec2.EC2Connection")
    @patch("boto.ec2.RegionInfo")
    def test_connection_http(self, region_mock, ec2_mock):
        m = Mock()
        region_mock.return_value = m
        os.environ["EC2_ENDPOINT"] = "http://amazonaws.com"
        ec2_mock.return_value = "connection to ec2"
        conn = ec2.EC2Manager(None).connection
        self.assertEqual("connection to ec2", conn)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com", port=80,
                                    path="/", is_secure=False,
                                    region=m)
        region_mock.assert_called_with(name="custom", endpoint="amazonaws.com")

    @patch("boto.ec2.EC2Connection")
    @patch("boto.ec2.RegionInfo")
    def test_connection_https(self, region_mock, ec2_mock):
        m = Mock()
        region_mock.return_value = m
        os.environ["EC2_ENDPOINT"] = "https://amazonaws.com"
        ec2_mock.return_value = "connection to ec2"
        conn = ec2.EC2Manager(None).connection
        self.assertEqual("connection to ec2", conn)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com", port=443,
                                    path="/", is_secure=True,
                                    region=m)
        region_mock.assert_called_with(name="custom", endpoint="amazonaws.com")

    @patch("boto.ec2.EC2Connection")
    @patch("boto.ec2.RegionInfo")
    def test_ec2_connection_http_custom_port(self, region_mock, ec2_mock):
        m = Mock()
        region_mock.return_value = m
        os.environ["EC2_ENDPOINT"] = "http://amazonaws.com:8080"
        ec2_mock.return_value = "connection to ec2"
        conn = ec2.EC2Manager(None).connection
        self.assertEqual("connection to ec2", conn)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com", port=8080,
                                    path="/", is_secure=False,
                                    region=m)
        region_mock.assert_called_with(name="custom", endpoint="amazonaws.com")

    @patch("boto.ec2.EC2Connection")
    @patch("boto.ec2.RegionInfo")
    def test_ec2_connection_https_custom_port(self, region_mock, ec2_mock):
        m = Mock()
        region_mock.return_value = m
        os.environ["EC2_ENDPOINT"] = "https://amazonaws.com:8080"
        ec2_mock.return_value = "connection to ec2"
        conn = ec2.EC2Manager(None).connection
        self.assertEqual("connection to ec2", conn)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com", port=8080,
                                    path="/", is_secure=True,
                                    region=m)
        region_mock.assert_called_with(name="custom", endpoint="amazonaws.com")

    @patch("boto.ec2.EC2Connection")
    @patch("boto.ec2.RegionInfo")
    def test_ec2_connection_custom_path(self, region_mock, ec2_mock):
        m = Mock()
        region_mock.return_value = m
        os.environ["EC2_ENDPOINT"] = "https://amazonaws.com:8080/something"
        ec2_mock.return_value = "connection to ec2"
        result = ec2.EC2Manager(None).connection
        self.assertEqual("connection to ec2", result)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com", port=8080,
                                    path="/something", is_secure=True,
                                    region=m)
        region_mock.assert_called_with(name="custom", endpoint="amazonaws.com")

    def test_add_instance(self):
        conn = Mock()
        conn.run_instances.return_value = self.get_fake_reservation(
            instances=[{"id": "i-800", "dns_name": "abcd.amazonaws.com"}],
        )
        storage = Mock()
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        manager.add_instance("someapp")
        conn.run_instances.assert_called_once_with(image_id=self.ami_id,
                                                   subnet_id=self.subnet_id,
                                                   user_data=None)
        storage.store.assert_called_once()

    @patch("sys.stderr")
    def test_add_instance_ec2_failure(self, stderr_mock):
        conn = Mock()
        conn.run_instances.side_effect = ValueError("Something went wrong")
        manager = ec2.EC2Manager(None)
        manager._connection = conn
        manager.add_instance("someapp")
        msg = "[ERROR] Failed to create EC2 instance: Something went wrong"
        stderr_mock.write.assert_called_with(msg)

    def test_add_instance_packages(self):
        os.environ["API_PACKAGES"] = "varnish vim-nox"

        def recover():
            del os.environ["API_PACKAGES"]
        self.addCleanup(recover)
        conn = Mock()
        conn.run_instances.return_value = self.get_fake_reservation(
            instances=[{"id": "i-800", "dns_name": "abcd.amazonaws.com"}],
        )
        storage = Mock()
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        manager.add_instance("someapp")
        user_data = """apt-get update
apt-get install -y varnish vim-nox
"""
        conn.run_instances.assert_called_once_with(image_id=self.ami_id,
                                                   subnet_id=self.subnet_id,
                                                   user_data=user_data)
        storage.store.assert_called_once()

    def test_remove_instance(self):
        conn = Mock()
        storage = Mock()
        storage.retrieve.return_value = api_storage.Instance(id="i-0800")
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        manager.remove_instance("someapp")
        conn.terminate_instances.assert_called_with(instance_ids=["i-0800"])
        storage.retrieve.assert_called_with(name="someapp")
        storage.remove.assert_called_with(name="someapp")

    @patch("sys.stderr")
    def test_remove_instance_ec2_failure(self, stderr_mock):
        conn = Mock()
        conn.terminate_instances.side_effect = ValueError("Something went wrong")
        manager = ec2.EC2Manager(Mock())
        manager._connection = conn
        manager.remove_instance("someapp")
        msg = "[ERROR] Failed to terminate EC2 instance: Something went wrong"
        stderr_mock.write.assert_called_with(msg)

    def test_bind_instance(self):
        conn = Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[{"id": "i-0800", "private_ip_address": "10.2.2.1"}],
        )]
        storage = Mock()
        storage.retrieve.return_value = api_storage.Instance(id="i-0800")
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        write_vcl = Mock()
        manager.write_vcl = write_vcl
        manager.bind("someapp", "myapp.cloud.tsuru.io")
        storage.retrieve.assert_called_with(name="someapp")
        conn.get_all_instances.assert_called_with(instance_ids=["i-0800"])
        write_vcl.assert_called_with("10.2.2.1", "myapp.cloud.tsuru.io")

    def test_bind_instance_no_reservation(self):
        conn = Mock()
        conn.get_all_instances.return_value = []
        storage = Mock()
        storage.retrieve.return_value = api_storage.Instance(id="i-0800")
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.bind("someapp", "yourapp.cloud.tsuru.io")

    def test_bind_instance_instances_not_found(self):
        conn = Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[],
        )]
        storage = Mock()
        storage.retrieve.return_value = api_storage.Instance(id="i-0800")
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.bind("someapp", "yourapp.cloud.tsuru.io")

    def test_unbind_instance(self):
        conn = Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[{"id": "i-0800", "private_ip_address": "10.2.2.1"}],
        )]
        storage = Mock()
        storage.retrieve.return_value = api_storage.Instance(id="i-0800")
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        remove_vcl = Mock()
        manager.remove_vcl = remove_vcl
        manager.unbind("someapp", "myapp.cloud.tsuru.io")
        storage.retrieve.assert_called_with(name="someapp")
        conn.get_all_instances.assert_called_with(instance_ids=["i-0800"])
        remove_vcl.assert_called_with("10.2.2.1")

    def test_unbind_instance_no_reservation(self):
        conn = Mock()
        conn.get_all_instances.return_value = []
        storage = Mock()
        storage.retrieve.return_value = api_storage.Instance(id="i-0800")
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.unbind("someapp", "yourapp.cloud.tsuru.io")

    def test_unbind_instance_instances_not_found(self):
        conn = Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[],
        )]
        storage = Mock()
        storage.retrieve.return_value = api_storage.Instance(id="i-0800")
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.unbind("someapp", "yourapp.cloud.tsuru.io")

    def test_vcl_template(self):
        manager = ec2.EC2Manager(None)
        self.assertEqual(ec2.VCL_TEMPLATE, manager.vcl_template())

    @patch("varnish.VarnishHandler")
    def test_write_vcl(self, VarnishHandler):
        os.environ["SECRET"] = "abc-def"

        def clean():
            del os.environ["SECRET"]
        self.addCleanup(clean)
        varnish_handler = Mock()
        VarnishHandler.return_value = varnish_handler
        app_host, instance_ip = "yeah.cloud.tsuru.io", "10.2.1.2"
        manager = ec2.EC2Manager(None)
        manager.write_vcl(instance_ip, app_host)
        vcl = manager.vcl_template().format(app_host)
        VarnishHandler.assert_called_with("{0}:6082".format(instance_ip),
                                          secret="abc-def")
        varnish_handler.vcl_inline.assert_called_with("feaas", vcl)
        varnish_handler.vcl_use.assert_called_with("feaas")
        varnish_handler.quit.assert_called()

    @patch("varnish.VarnishHandler")
    def test_remove_vcl(self, VarnishHandler):
        os.environ["SECRET"] = "abc123"

        def clean():
            del os.environ["SECRET"]
        self.addCleanup(clean)
        varnish_handler = Mock()
        VarnishHandler.return_value = varnish_handler
        instance_ip = "10.2.2.1"
        manager = ec2.EC2Manager(None)
        manager.remove_vcl(instance_ip)
        VarnishHandler.assert_called_with("10.2.2.1:6082", secret="abc123")
        varnish_handler.vcl_use.assert_called_with("boot")
        varnish_handler.vcl_discard.assert_called_with("feaas")
        varnish_handler.quit.assert_called()

    def test_info(self):
        instance = api_storage.Instance("secret", "secret.cloud.tsuru.io", "i-0800")
        storage = Mock()
        storage.retrieve.return_value = instance
        manager = ec2.EC2Manager(storage)
        info = manager.info("secret")
        self.assertEqual(instance.to_dict(), info)
        storage.retrieve.assert_called_with("secret")

    def test_info_instance_not_found(self):
        storage = Mock()
        storage.retrieve.side_effect = api_storage.InstanceNotFoundError()
        manager = ec2.EC2Manager(storage)
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.info("secret")

    def test_status_running(self):
        conn = Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[{"id": "i-0800", "private_ip_address": "10.2.2.1",
                        "state": "running", "state_code": 16}],
        )]
        instance = api_storage.Instance("secret", "secret.cloud.tsuru.io", "i-0800")
        storage = Mock()
        storage.retrieve.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        status = manager.status("secret")
        self.assertEqual("running", status)

    def test_status_not_running(self):
        conn = Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[{"id": "i-0800", "private_ip_address": "10.2.2.1",
                        "state": "pending", "state_code": 0}],
        )]
        instance = api_storage.Instance("secret", "secret.cloud.tsuru.io", "i-0800")
        storage = Mock()
        storage.retrieve.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        status = manager.status("secret")
        self.assertEqual("pending", status)

    def test_status_instance_not_found_in_storage(self):
        storage = Mock()
        storage.retrieve.side_effect = api_storage.InstanceNotFoundError()
        manager = ec2.EC2Manager(storage)
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.status("secret")

    def test_status_instance_not_found_in_ec2_reservation(self):
        conn = Mock()
        conn.get_all_instances.return_value = []
        instance = api_storage.Instance("secret", "secret.cloud.tsuru.io", "i-0800")
        storage = Mock()
        storage.retrieve.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.status("secret")

    def test_status_instance_not_found_in_ec2_instances(self):
        conn = Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[],
        )]
        instance = api_storage.Instance("secret", "secret.cloud.tsuru.io", "i-0800")
        storage = Mock()
        storage.retrieve.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.status("secret")

    def get_fake_reservation(self, instances):
        reservation = Mock(instances=[])
        for instance in instances:
            reservation.instances.append(Mock(**instance))
        return reservation
