# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os
import unittest

import mock

from feaas import managers, storage as api_storage
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

    @mock.patch("boto.ec2.EC2Connection")
    @mock.patch("boto.ec2.RegionInfo")
    def test_connection_http(self, region_mock, ec2_mock):
        m = mock.Mock()
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

    @mock.patch("boto.ec2.EC2Connection")
    @mock.patch("boto.ec2.RegionInfo")
    def test_connection_https(self, region_mock, ec2_mock):
        m = mock.Mock()
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

    @mock.patch("boto.ec2.EC2Connection")
    @mock.patch("boto.ec2.RegionInfo")
    def test_ec2_connection_http_custom_port(self, region_mock, ec2_mock):
        m = mock.Mock()
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

    @mock.patch("boto.ec2.EC2Connection")
    @mock.patch("boto.ec2.RegionInfo")
    def test_ec2_connection_https_custom_port(self, region_mock, ec2_mock):
        m = mock.Mock()
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

    @mock.patch("boto.ec2.EC2Connection")
    @mock.patch("boto.ec2.RegionInfo")
    def test_ec2_connection_custom_path(self, region_mock, ec2_mock):
        m = mock.Mock()
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

    def test_start_instance(self):
        instance = api_storage.Instance(name="myapp")
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager._add_units = mock.Mock()
        created_instance = manager.start_instance("myapp")
        self.assertEqual(instance, created_instance)
        manager._add_units.assert_called_with(instance, 1)

    def test_start_instance_not_found(self):
        storage = mock.Mock()
        storage.retrieve_instance.side_effect = api_storage.InstanceNotFoundError()
        manager = ec2.EC2Manager(storage)
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.start_instance("myapp")

    @mock.patch("uuid.uuid4")
    def test_start_instance_ec2_default_userdata(self, uuid4):
        uuid4.return_value = u"abacaxi"
        os.environ["API_PACKAGES"] = "varnish vim-nox"

        def recover():
            del os.environ["API_PACKAGES"]
        self.addCleanup(recover)
        conn = mock.Mock()
        conn.run_instances.return_value = self.get_fake_reservation(
            instances=[{"id": "i-800", "dns_name": "abcd.amazonaws.com"}],
        )
        manager = ec2.EC2Manager(None)
        manager._connection = conn
        manager._run_unit()
        user_data = """apt-get update
apt-get install -y varnish vim-nox
sed -i -e 's/-T localhost:6082/-T :6082/' /etc/default/varnish
sed -i -e 's/-a :6081/-a :8080/' /etc/default/varnish
echo abacaxi > /etc/varnish/secret
service varnish restart
cat > /etc/cron.hourly/dump_vcls <<'END'
{0}
END
chmod +x /etc/cron.hourly/dump_vcls
""".format(open(managers.DUMP_VCL_FILE).read())
        conn.run_instances.assert_called_once_with(image_id=self.ami_id,
                                                   subnet_id=self.subnet_id,
                                                   user_data=user_data)

    @mock.patch("httplib2.Http.request")
    @mock.patch("uuid.uuid4")
    def test_start_instance_ec2_custom_userdata(self, uuid4, request):
        uuid4.return_value = u"abacaxi"
        return_content = """apt-get update
apt-get install -y varnish vim-nox
sed -i -e 's/-T localhost:6082/-T :6082/' /etc/default/varnish
sed -i -e 's/-a :6081/-a :8080/' /etc/default/varnish
echo VARNISH_SECRET_KEY > /etc/varnish/secret
service varnish restart
cat > /etc/cron.hourly/dump_vcls <<'END'
{0}
END
chmod +x /etc/cron.hourly/dump_vcls
""".format(open(managers.DUMP_VCL_FILE).read())
        request.return_value = (200, return_content)
        os.environ["USER_DATA_URL"] = "http://localhost/custom_user_data_script"

        def recover():
            del os.environ["USER_DATA_URL"]
        self.addCleanup(recover)
        conn = mock.Mock()
        conn.run_instances.return_value = self.get_fake_reservation(
            instances=[{"id": "i-800", "dns_name": "abcd.amazonaws.com"}],
        )
        manager = ec2.EC2Manager(None)
        manager._connection = conn
        manager._run_unit()
        user_data = """apt-get update
apt-get install -y varnish vim-nox
sed -i -e 's/-T localhost:6082/-T :6082/' /etc/default/varnish
sed -i -e 's/-a :6081/-a :8080/' /etc/default/varnish
echo abacaxi > /etc/varnish/secret
service varnish restart
cat > /etc/cron.hourly/dump_vcls <<'END'
{0}
END
chmod +x /etc/cron.hourly/dump_vcls
""".format(open(managers.DUMP_VCL_FILE).read())
        conn.run_instances.assert_called_once_with(image_id=self.ami_id,
                                                   subnet_id=self.subnet_id,
                                                   user_data=user_data)

    def test_remove_instance(self):
        instance = api_storage.Instance(name="secret")
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager.remove_instance("secret")
        self.assertEqual("removed", instance.state)
        storage.retrieve_instance.assert_called_with(name="secret")
        storage.store_instance.assert_called_with(instance)

    def test_remove_instance_not_found(self):
        storage = mock.Mock()
        storage.retrieve_instance.side_effect = api_storage.InstanceNotFoundError()
        manager = ec2.EC2Manager(storage)
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.remove_instance("secret")

    def test_terminate_instance(self):
        conn = mock.Mock()
        storage = mock.Mock()
        unit = api_storage.Unit(id="i-0800")
        instance = api_storage.Instance(name="secret", units=[unit])
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        got_instance = manager.terminate_instance("secret")
        conn.terminate_instances.assert_called_with(instance_ids=["i-0800"])
        storage.retrieve_instance.assert_called_with(name="secret")
        self.assertEqual(instance, got_instance)

    def test_terminate_instance_not_found(self):
        storage = mock.Mock()
        storage.retrieve_instance.side_effect = api_storage.InstanceNotFoundError()
        manager = ec2.EC2Manager(storage)
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.terminate_instance("secret")

    @mock.patch("sys.stderr")
    def test_terminate_instance_ec2_failure(self, stderr_mock):
        conn = mock.Mock()
        conn.terminate_instances.side_effect = ValueError("Something went wrong")
        unit = api_storage.Unit(id="i-0800")
        storage = mock.Mock()
        storage.retrieve_instance.return_value = api_storage.Instance(name="secret",
                                                                      units=[unit])
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        manager.terminate_instance("someapp")
        msg = "[ERROR] Failed to terminate EC2 instance: Something went wrong"
        stderr_mock.write.assert_called_with(msg)

    def test_physical_scale_add_units(self):
        instance = api_storage.Instance(name="secret",
                                        units=[api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                                                id="i-0800")])
        fake_run_unit, fake_data = self.get_fake_run_unit()
        storage = mock.Mock()
        manager = ec2.EC2Manager(storage)
        manager._run_unit = fake_run_unit
        units = manager.physical_scale(instance, 4)
        self.assertEqual(fake_data["calls"], 3)
        instance.units.extend(fake_data["units"])
        storage.store_instance.assert_called_with(instance)
        self.assertEqual(fake_data["units"], units)

    def test_physical_scale_remove_units(self):
        unit1 = api_storage.Unit(dns_name="secret1.cloud.tsuru.io", id="i-0800")
        unit2 = api_storage.Unit(dns_name="secret2.cloud.tsuru.io", id="i-0801")
        unit3 = api_storage.Unit(dns_name="secret3.cloud.tsuru.io", id="i-0802")
        units = [unit1, unit2, unit3]
        instance = api_storage.Instance(name="secret", units=units)
        storage = mock.Mock()
        manager = ec2.EC2Manager(storage)
        manager._terminate_unit = mock.Mock()
        units = manager.physical_scale(instance, 1)
        expected = [mock.call(unit1), mock.call(unit2)]
        self.assertEqual(expected, manager._terminate_unit.call_args_list)
        self.assertEqual([unit3], instance.units)
        storage.store_instance.assert_called_with(instance)
        self.assertEqual([unit1, unit2], units)

    def get_fake_reservation(self, instances):
        reservation = mock.Mock(instances=[])
        for instance in instances:
            reservation.instances.append(mock.Mock(**instance))
        return reservation

    def get_fake_run_unit(self):
        fake_data = {"calls": 0, "units": []}

        def fake_run_unit():
            calls = fake_data["calls"] = fake_data["calls"] + 1
            name = "i-080%d" % calls
            unit = api_storage.Unit(id=name, dns_name="%s.domain.com" % name,
                                    secret="%s-secret" % name)
            fake_data["units"].append(unit)
            return unit
        return fake_run_unit, fake_data
