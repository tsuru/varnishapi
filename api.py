import os
import sqlite3
from flask import Flask, request

api = Flask(__name__)
access_key = os.environ.get("ACCESS_KEY")
secret_key = os.environ.get("SECRET_KEY")
ami_id = os.environ.get("AMI_ID")
subnet_id = os.environ.get("SUBNET_ID")
default_db_name = "varnishapi.db"


@api.route("/resources", methods=["POST"])
def create_instance():
    reservations = _create_ec2_instance()
    _store_instance_and_app(reservations, request.form.get("name")) # check if name is present
    return "", 201


def _create_ec2_instance():
    from boto.ec2.connection import EC2Connection
    conn = EC2Connection(access_key, secret_key)
    return conn.run_instances(image_id=ami_id, subnet_id=subnet_id)


def _store_instance_and_app(reservations, app_name):
    instance_apps = []
    for r in reservations:
        for i in r.instances:
            instance_apps.append((i.id, app_name))
    c = conn.cursor()
    c.executemany("insert into instance_app values (?, ?)", instance_apps)
    conn.commit()


def _get_database_name():
    if os.environ.get("DB_PATH"): # this env var should be an absolute path
        return os.environ["DB_PATH"]
    return os.path.realpath(os.path.join(__file__, "../", default_db_name))


conn = sqlite3.connect(_get_database_name())
if __name__ == "__main__":
    api.run()
