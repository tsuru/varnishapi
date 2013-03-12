import api
import os
import unittest
from mock import patch
from collections import namedtuple


class DatabaseTest(object):

    @classmethod
    def setUpClass(cls):
        os.environ["DB_PATH"] = ":memory:"
        sql_path = os.path.realpath(os.path.join(__file__, "../database.sql"))
        f = open(sql_path)
        sql = f.read().replace("\n", "")
        c = api.conn.cursor()
        c.execute(sql)

    @classmethod
    def tearDownClass(cls):
        c = api.conn.cursor()
        c.execute("drop table instance_app;")
        api.conn.close()


class CreateInstanceTestCase(DatabaseTest, unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.api = api.api.test_client()
        os.environ["ACCESS_KEY"] = "access"
        os.environ["SECRET_KEY"] = "secret"
        os.environ["AMI_ID"] = "ami-123"
        os.environ["SUBNET_ID"] = "subnet-123"
        reload(api)
        DatabaseTest.setUpClass()

    def tearDown(self):
        c = api.conn.cursor()
        c.execute("delete from instance_app;")

    @classmethod
    def tearDownClass(cls):
        os.environ["ACCESS_KEY"] = ""
        os.environ["SECRET_KEY"] = ""
        os.environ["AMI_ID"] = ""
        DatabaseTest.tearDownClass()

    def fake_reservation(self):
        Reservation = namedtuple("Reservation", ["instances"])
        Instance = namedtuple("Instance", ["id"])
        return Reservation(instances=[Instance(id="i-1")])

    @patch("boto.ec2.connection.EC2Connection")
    def test_create_instance_should_return_201(self, mock):
        resp = self.api.post("/resources", data={"name": "someapp"})
        self.assertEqual(resp.status_code, 201)

    @patch("boto.ec2.connection.EC2Connection")
    def test_should_connect_with_ec2_using_environment_variables(self, mock):
        self.api.post("/resources", data={"name": "someapp"})
        mock.assert_called_once_with(api.access_key, api.secret_key)

    @patch("boto.ec2.connection.EC2Connection")
    def test_should_create_instance_on_ec2(self, mock):
        instance = mock.return_value
        r = self.fake_reservation()
        instance.run_instances.return_value = [r]
        self.api.post("/resources", data={"name": "someapp"})
        self.assertTrue(instance.run_instances.called)

    @patch("boto.ec2.connection.EC2Connection")
    def test_should_create_instance_on_ec2_using_subnet_and_ami_defined_in_env_var(self, mock):
        instance = mock.return_value
        self.api.post("/resources", data={"name": "someapp"})
        instance.run_instances.assert_called_once_with(image_id=api.ami_id, subnet_id=api.subnet_id)

    @patch("boto.ec2.connection.EC2Connection")
    def test_should_store_instance_id_and_app_name_on_database(self, mock):
        instance = mock.return_value
        r = self.fake_reservation()
        instance.run_instances.return_value = [r]
        self.api.post("/resources", data={"name": "someapp"})
        c = api.conn.cursor()
        c.execute("select * from instance_app;")
        result = c.fetchall()
        expected = [("i-1", "someapp")]
        self.assertListEqual(expected, result)


class DeleteInstanceTestCase(DatabaseTest, unittest.TestCase):

    pass


class HelpersTestcase(unittest.TestCase):

    def test_get_database_name_should_return_absolute_path_to_it(self):
        del os.environ["DB_PATH"]
        db_name = api._get_database_name()
        expected = os.path.realpath(os.path.join(__file__, "../", api.default_db_name))
        self.assertEqual(expected, db_name)

    def test_get_database_name_should_use_DB_PATH_env_var_when_its_set(self):
        os.environ["DB_PATH"] = ":memory:"
        reload(api)
        got = api._get_database_name()
        self.assertEqual(os.environ["DB_PATH"], got)
        del os.environ["DB_PATH"]



if __name__ == "__main__":
    unittest.main()
