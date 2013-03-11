import os
from flask import Flask

api = Flask(__name__)
access_key = os.environ.get("ACCESS_KEY")
secret_key = os.environ.get("SECRET_KEY")
ami_id = os.environ.get("AMI_ID")


@api.route("/resources", methods=["POST"])
def create_instance():
    _create_ec2_instance()
    return "", 201


def _create_ec2_instance():
    from boto.ec2.connection import EC2Connection
    conn = EC2Connection(access_key, secret_key)
    conn.run_instances(image_id=ami_id)


if __name__ == "__main__":
    api.run()
