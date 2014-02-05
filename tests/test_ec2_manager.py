# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os
import unittest

from mock import Mock, patch

from varnishapi.managers import ec2


class EC2ManagerTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["EC2_ACCESS_KEY"] = cls.access_key = "access"
        os.environ["EC2_SECRET_KEY"] = cls.secret_key = "secret"
        os.environ["AMI_ID"] = cls.ami_id = "ami-123"
        os.environ["SUBNET_ID"] = cls.subnet_id = "subnet-123"
        os.environ["KEY_PATH"] = cls.key_path = "/tmp/testkey.pub"
        f = file(cls.key_path, "w")
        f.write("testkey 123")
        f.close()

    def setUp(self):
        os.environ["EC2_ENDPOINT"] = "http://amazonaws.com"

    @patch("boto.ec2.EC2Connection")
    def test_connection_http(self, ec2_mock):
        os.environ["EC2_ENDPOINT"] = "http://amazonaws.com"
        ec2_mock.return_value = "connection to ec2"
        conn = ec2.EC2Manager(None).connection
        self.assertEqual("connection to ec2", conn)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com",
                                    port=80,
                                    path="/",
                                    is_secure=False)

    @patch("boto.ec2.EC2Connection")
    def test_connection_https(self, ec2_mock):
        os.environ["EC2_ENDPOINT"] = "https://amazonaws.com"
        ec2_mock.return_value = "connection to ec2"
        conn = ec2.EC2Manager(None).connection
        self.assertEqual("connection to ec2", conn)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com",
                                    port=443,
                                    path="/",
                                    is_secure=True)

    @patch("boto.ec2.EC2Connection")
    def test_ec2_connection_http_custom_port(self, ec2_mock):
        os.environ["EC2_ENDPOINT"] = "http://amazonaws.com:8080"
        ec2_mock.return_value = "connection to ec2"
        conn = ec2.EC2Manager(None).connection
        self.assertEqual("connection to ec2", conn)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com",
                                    port=8080,
                                    path="/",
                                    is_secure=False)

    @patch("boto.ec2.EC2Connection")
    def test_ec2_connection_https_custom_port(self, ec2_mock):
        os.environ["EC2_ENDPOINT"] = "https://amazonaws.com:8080"
        ec2_mock.return_value = "connection to ec2"
        conn = ec2.EC2Manager(None).connection
        self.assertEqual("connection to ec2", conn)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com",
                                    port=8080,
                                    path="/",
                                    is_secure=True)

    @patch("boto.ec2.EC2Connection")
    def test_ec2_connection_custom_path(self, ec2_mock):
        os.environ["EC2_ENDPOINT"] = "https://amazonaws.com:8080/something"
        ec2_mock.return_value = "connection to ec2"
        result = ec2.EC2Manager(None).connection
        self.assertEqual("connection to ec2", result)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com",
                                    port=8080,
                                    path="/something",
                                    is_secure=True)

    def test_add_instance(self):
        conn = Mock()
        conn.run_instances.return_value = self.get_fake_reservation(
            instances=[{"id": "i-800", "dns_name": "abcd.amazonaws.com"}],
        )
        storage = Mock()
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        manager.add_instance("someapp")
        f = open(self.key_path)
        key = f.read()
        f.close()
        user_data = """#cloud-config
ssh_authorized_keys: ['{0}']
""".format(key)
        conn.run_instances.assert_called_once_with(image_id=self.ami_id,
                                                   subnet_id=self.subnet_id,
                                                   user_data=user_data)
        storage.store.assert_called_with(instance_id="i-800",
                                         dns_name="abcd.amazonaws.com",
                                         name="someapp")

    @patch("syslog.syslog")
    def test_add_instance_ec2_failure(self, syslog_mock):
        import syslog as original_syslog
        conn = Mock()
        conn.run_instances.side_effect = ValueError("Something went wrong")
        manager = ec2.EC2Manager(None)
        manager._connection = conn
        manager.add_instance("someapp")
        msg = "Failed to create EC2 instance: Something went wrong"
        syslog_mock.assert_called_with(original_syslog.LOG_ERR, msg)

    def test_remove_instance(self):
        conn = Mock()
        storage = Mock()
        storage.retrieve.return_value = "i-0800"
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        manager.remove_instance("someapp")
        conn.terminate_instances.assert_called_with(instance_ids=["i-0800"])
        storage.retrieve.assert_called_with(name="someapp")
        storage.remove.assert_called_with(name="someapp")

    @patch("syslog.syslog")
    def test_remove_instance_ec2_failure(self, syslog_mock):
        import syslog as original_syslog
        conn = Mock()
        conn.terminate_instances.side_effect = ValueError("Something went wrong")
        manager = ec2.EC2Manager(Mock())
        manager._connection = conn
        manager.remove_instance("someapp")
        msg = "Failed to terminate EC2 instance: Something went wrong"
        syslog_mock.assert_called_with(original_syslog.LOG_ERR, msg)

    def test_bind_instance(self):
        conn = Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[{"id": "i-0800", "private_ip_address": "10.2.2.1"}],
        )]
        storage = Mock()
        storage.retrieve.return_value = "i-0800"
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
        storage.retrieve.return_value = "i-0800"
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        with self.assertRaises(ValueError) as cm:
            manager.bind("someapp", "yourapp.cloud.tsuru.io")
        exc = cm.exception
        self.assertEqual(("Instance not found",),
                         exc.args)

    def test_bind_instance_instances_not_found(self):
        conn = Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[],
        )]
        storage = Mock()
        storage.retrieve.return_value = "i-0800"
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        with self.assertRaises(ValueError) as cm:
            manager.bind("someapp", "yourapp.cloud.tsuru.io")
        exc = cm.exception
        self.assertEqual(("Instance not found",),
                         exc.args)

    @patch("subprocess.call")
    def test_write_vcl(self, sp_mock):
        sp_mock.return_value = 0
        app_host = "myapp.cloud.tsuru.io"
        instance_ip = "10.2.2.1"
        manager = ec2.EC2Manager(None)
        manager.write_vcl(instance_ip, app_host)
        cmd = "sudo bash -c \"echo '{0}' > /etc/varnish/default.vcl && service varnish reload\""
        cmd = cmd.format(ec2.VCL_TEMPLATE.format(app_host))
        expected = ["ssh", instance_ip, "-l", "ubuntu", "-o", "StrictHostKeyChecking no", cmd]
        cmd_arg = sp_mock.call_args_list[0][0][0]
        self.assertEqual(expected, cmd_arg)

    @patch("subprocess.call")
    @patch("syslog.syslog")
    def test_write_vcl_failure_stdout(self, syslog_mock, sp_mock):
        def side_effect(*args, **kwargs):
            kwargs["stdout"].write("something went wrong")
        sp_mock.side_effect = side_effect
        sp_mock.return_value = 1
        app_host = "myapp.cloud.tsuru.io"
        instance_ip = "10.2.2.1"
        manager = ec2.EC2Manager(None)
        with self.assertRaises(Exception) as cm:
            manager.write_vcl(instance_ip, app_host)
        exc = cm.exception
        self.assertEqual(("Could not connect to the service instance",),
                         exc.args)
        import syslog as original_syslog
        msg = "Failed to write VCL file in the instance {0}: something went wrong"
        syslog_mock.assert_called_with(original_syslog.LOG_ERR,
                                       msg.format(instance_ip))

    @patch("subprocess.call")
    @patch("syslog.syslog")
    def test_write_vcl_failure_stderr(self, syslog_mock, sp_mock):
        def side_effect(*args, **kwargs):
            kwargs["stderr"].write("something went wrong")
        sp_mock.side_effect = side_effect
        sp_mock.return_value = 1
        app_host = "myapp.cloud.tsuru.io"
        instance_ip = "10.2.2.1"
        manager = ec2.EC2Manager(None)
        with self.assertRaises(Exception):
            manager.write_vcl(instance_ip, app_host)
        import syslog as original_syslog
        msg = "Failed to write VCL file in the instance {0}: something went wrong"
        syslog_mock.assert_called_with(original_syslog.LOG_ERR,
                                       msg.format(instance_ip))

    def get_fake_reservation(self, instances):
        reservation = Mock(instances=[])
        for instance in instances:
            reservation.instances.append(Mock(**instance))
        return reservation
