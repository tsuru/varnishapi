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
        conn = ec2.EC2Manager().connection
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
        conn = ec2.EC2Manager().connection
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
        conn = ec2.EC2Manager().connection
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
        conn = ec2.EC2Manager().connection
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
        result = ec2.EC2Manager().connection
        self.assertEqual("connection to ec2", result)
        ec2_mock.assert_called_with(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key,
                                    host="amazonaws.com",
                                    port=8080,
                                    path="/something",
                                    is_secure=True)

    def test_add_instances_ec2_parameters(self):
        conn = Mock()
        manager = ec2.EC2Manager()
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

    @patch("syslog.syslog")
    def test_add_instances_ec2_failure(self, syslog_mock):
        import syslog as original_syslog
        conn = Mock()
        conn.run_instances.side_effect = ValueError("Something went wrong")
        manager = ec2.EC2Manager()
        manager._connection = conn
        manager.add_instance("someapp")
        msg = "Failed to create EC2 instance: Something went wrong"
        syslog_mock.assert_called_with(original_syslog.LOG_ERR, msg)
