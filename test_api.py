import os
import unittest
import api
from mock import patch
from collections import namedtuple


class ApiTestCase(unittest.TestCase):

    def setUp(self):
        self.api = api.api.test_client()
        os.environ["ACCESS_KEY"] = "access"
        os.environ["SECRET_KEY"] = "secret"
        os.environ["AMI_ID"] = "ami-123"

    @patch("boto.ec2.connection.EC2Connection")
    def test_create_instance_should_return_201(self, mock):
        resp = self.api.post("/resources", data={"name": "someapp"})
        self.assertEqual(resp.status_code, 201)

    @patch("boto.ec2.connection.EC2Connection")
    def test_should_create_instance_on_ec2(self, mock):
        instance = mock.return_value
        Reservation = namedtuple("Reservation", ["instances"])
        Instance = namedtuple("Instance", ["id"])
        inst = Instance(id="i-1")
        r = Reservation(instances=[inst])
        instance.run_instances.return_value = [r]
        self.api.post("/resources", data={"name": "someapp"})
        self.assertTrue(instance.run_instances.called)


if __name__ == "__main__":
    unittest.main()
