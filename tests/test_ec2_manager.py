# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os
import unittest

import mock

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

    def test_new_instance(self):
        storage = mock.Mock()
        storage.retrieve_instance.side_effect = api_storage.InstanceNotFoundError()
        manager = ec2.EC2Manager(storage)
        instance = manager.new_instance("someapp")
        storage.store_instance.assert_called_with(instance)

    def test_add_duplicate_instance(self):
        storage = mock.Mock()
        storage.retrieve_instance.return_value = "instance"
        manager = ec2.EC2Manager(storage)
        with self.assertRaises(api_storage.InstanceAlreadyExistsError):
            manager.new_instance("pull")

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
    def test_start_instance_ec2(self, uuid4):
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
""".format(open(ec2.DUMP_VCL_FILE).read())
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
        storage.retrieve_instance.return_value = api_storage.Instance(name="secret",
                                                                      units=[unit])
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        manager.terminate_instance("secret")
        conn.terminate_instances.assert_called_with(instance_ids=["i-0800"])
        storage.retrieve_instance.assert_called_with(name="secret")

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

    @mock.patch("feaas.storage.Bind")
    def test_bind_instance(self, Bind):
        Bind.return_value = "abacaxi"
        instance = api_storage.Instance(name="myinstance",
                                        units=[api_storage.Unit(secret="abc-123",
                                                                dns_name="10.1.1.2",
                                                                id="i-0800")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager.bind("someapp", "myapp.cloud.tsuru.io")
        storage.retrieve_instance.assert_called_with(name="someapp")
        storage.store_bind.assert_called_with("abacaxi")
        Bind.assert_called_with("myapp.cloud.tsuru.io", instance)

    @mock.patch("feaas.storage.Bind")
    def test_unbind_instance(self, Bind):
        Bind.return_value = "abacaxi"
        instance = api_storage.Instance(name="myinstance",
                                        units=[api_storage.Unit(id="i-0800",
                                                                secret="abc-123",
                                                                dns_name="10.1.1.2")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        remove_vcl = mock.Mock()
        manager.remove_vcl = remove_vcl
        manager.unbind("someapp", "myapp.cloud.tsuru.io")
        storage.retrieve_instance.assert_called_with(name="someapp")
        storage.remove_bind.assert_called_with("abacaxi")
        Bind.assert_called_with("myapp.cloud.tsuru.io", instance)
        remove_vcl.assert_called_with("10.1.1.2", "abc-123")

    def test_vcl_template(self):
        manager = ec2.EC2Manager(None)
        with open(ec2.VCL_TEMPLATE_FILE) as f:
            content = f.read().replace("\n", " ").replace('"', r'\"')
            content = content.replace("\t", "")
            self.assertEqual('"%s"' % content.strip(),
                             manager.vcl_template())

    @mock.patch("varnish.VarnishHandler")
    def test_write_vcl(self, VarnishHandler):
        varnish_handler = mock.Mock()
        VarnishHandler.return_value = varnish_handler
        app_host, instance_ip = "yeah.cloud.tsuru.io", "10.2.1.2"
        manager = ec2.EC2Manager(None)
        manager.write_vcl(instance_ip, "abc-def", app_host)
        vcl = manager.vcl_template() % {"app_host": app_host}
        VarnishHandler.assert_called_with("{0}:6082".format(instance_ip),
                                          secret="abc-def")
        varnish_handler.vcl_inline.assert_called_with("feaas", vcl)
        varnish_handler.vcl_use.assert_called_with("feaas")
        varnish_handler.quit.assert_called()

    @mock.patch("varnish.VarnishHandler")
    def test_remove_vcl(self, VarnishHandler):
        varnish_handler = mock.Mock()
        VarnishHandler.return_value = varnish_handler
        instance_ip = "10.2.2.1"
        manager = ec2.EC2Manager(None)
        manager.remove_vcl(instance_ip, "abc123")
        VarnishHandler.assert_called_with("10.2.2.1:6082", secret="abc123")
        varnish_handler.vcl_use.assert_called_with("boot")
        varnish_handler.vcl_discard.assert_called_with("feaas")
        varnish_handler.quit.assert_called()

    def test_info(self):
        instance = api_storage.Instance(name="secret",
                                        units=[api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                                                id="i-0800")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        expected = [{"label": "Address", "value": "secret.cloud.tsuru.io"}]
        self.assertEqual(expected, manager.info("secret"))
        storage.retrieve_instance.assert_called_with(name="secret")

    def test_info_multiple_units(self):
        units = [api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                  id="i-0800"),
                 api_storage.Unit(dns_name="not-secret.cloud.tsuru.io",
                                  id="i-0800")]
        instance = api_storage.Instance(name="secret", units=units)
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        expected = [{"label": "Address", "value": "secret.cloud.tsuru.io"}]
        self.assertEqual(expected, manager.info("secret"))
        storage.retrieve_instance.assert_called_with(name="secret")

    def test_info_instance_not_found(self):
        storage = mock.Mock()
        storage.retrieve_instance.side_effect = api_storage.InstanceNotFoundError()
        manager = ec2.EC2Manager(storage)
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.info("secret")

    def test_status_running(self):
        conn = mock.Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[{"id": "i-0800", "private_ip_address": "10.2.2.1",
                        "state": "running", "state_code": 16}],
        )]
        instance = api_storage.Instance(name="secret",
                                        units=[api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                                                id="i-0800")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        status = manager.status("secret")
        self.assertEqual("running", status)

    def test_status_not_running(self):
        conn = mock.Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[{"id": "i-0800", "private_ip_address": "10.2.2.1",
                        "state": "pending", "state_code": 0}],
        )]
        instance = api_storage.Instance(name="secret",
                                        units=[api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                                                id="i-0800")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        status = manager.status("secret")
        self.assertEqual("pending", status)

    def test_status_instance_not_found_in_storage(self):
        storage = mock.Mock()
        storage.retrieve_instance.side_effect = api_storage.InstanceNotFoundError()
        manager = ec2.EC2Manager(storage)
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.status("secret")

    def test_status_instance_not_found_in_ec2_reservation(self):
        conn = mock.Mock()
        conn.get_all_instances.return_value = []
        instance = api_storage.Instance(name="secret",
                                        units=[api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                                                id="i-0800")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.status("secret")

    def test_status_instance_not_found_in_ec2_instances(self):
        conn = mock.Mock()
        conn.get_all_instances.return_value = [self.get_fake_reservation(
            instances=[],
        )]
        instance = api_storage.Instance(name="secret",
                                        units=[api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                                                id="i-0800")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager._connection = conn
        with self.assertRaises(api_storage.InstanceNotFoundError):
            manager.status("secret")

    def test_scale_instance(self):
        instance = api_storage.Instance(name="secret", state="started")
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        manager.scale_instance("secret", 2)
        storage.store_scale_job.assert_called_with({"instance": "secret",
                                                    "quantity": 2,
                                                    "state": "pending"})

    def test_scale_instance_already_scaling(self):
        instance = api_storage.Instance(name="secret", state="scaling")
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        with self.assertRaises(ValueError) as cm:
            manager.scale_instance("secret", 2)
        exc = cm.exception
        self.assertEqual(("instance is already scaling",), exc.args)

    def test_scale_instance_no_change(self):
        instance = api_storage.Instance(name="secret",
                                        units=[api_storage.Unit(dns_name="secret.cloud.tsuru.io",
                                                                id="i-0800"),
                                               api_storage.Unit(dns_name="secreti.cloud.tsuru.io",
                                                                id="i-0801")])
        storage = mock.Mock()
        storage.retrieve_instance.return_value = instance
        manager = ec2.EC2Manager(storage)
        with self.assertRaises(ValueError) as cm:
            manager.scale_instance("secret", 2)
        exc = cm.exception
        self.assertEqual(("instance already have 2 units",), exc.args)
        storage.retrieve_instance.assert_called_with(name="secret")

    def test_scale_instance_negative_quantity(self):
        manager = ec2.EC2Manager(None)
        with self.assertRaises(ValueError) as cm:
            manager.scale_instance("myapp", -1)
        exc = cm.exception
        self.assertEqual(("quantity must be a positive integer",), exc.args)

    def test_scale_instance_zero_quantity(self):
        manager = ec2.EC2Manager(None)
        with self.assertRaises(ValueError) as cm:
            manager.scale_instance("myapp", 0)
        exc = cm.exception
        self.assertEqual(("quantity must be a positive integer",), exc.args)

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
