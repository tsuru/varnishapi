import os
import sqlite3
import subprocess
import syslog
from md5 import md5
from flask import Flask, request

api = Flask(__name__)
access_key = os.environ.get("EC2_ACCESS_KEY")
secret_key = os.environ.get("EC2_SECRET_KEY")
region = os.environ.get("EC2_REGION", "sa-east-1")
ami_id = os.environ.get("AMI_ID")
subnet_id = os.environ.get("SUBNET_ID")
key_path = os.environ.get("KEY_PATH", os.path.expanduser("~/.ssh/id_rsa.pub"))
default_db_name = "varnishapi.db"
vcl_template = """backend default {{
    .host = \\"{0}\\";
    .port = \\"80\\";
}}
"""


@api.route("/resources", methods=["POST"])
def create_instance():
    try:
        reservation = _create_ec2_instance()
        _store_instance_and_app(reservation, request.form.get("name"))  # check if name is present
    except Exception:
        return "Caught error while creating service instance.", 500
    return "", 201


@api.route("/resources/<name>", methods=["DELETE"])
def delete_instance(name):
    instance_id = _get_instance_id(service_instance=name)
    _delete_ec2_instance(instance_id=instance_id)
    _delete_from_database(name)
    return "", 200


@api.route("/resources/<name>", methods=["POST"])
def bind(name):
    i_id = _get_instance_id(service_instance=name)
    i_ip = _get_instance_ip(instance_id=i_id)
    app_ip = request.form.get("app-host")
    _update_vcl_file(instance_address=i_ip, app_address=app_ip)
    return "null", 201


@api.route("/resources/<name>/hostname/<host>", methods=["DELETE"])
def unbind(name, host):
    i_id = _get_instance_id(service_instance=name)
    i_ip = _get_instance_ip(instance_id=i_id)
    _clean_vcl_file(instance_address=i_ip)
    return "", 200


def _get_instance_ip(instance_id):
    conn = _ec2_connection()
    reservations = conn.get_all_instances(instance_ids=[instance_id])
    if len(reservations) != 1 or len(reservations[0].instances) != 1:
        return ""  # throw exception?
    return reservations[0].instances[0].private_ip_address


def _rand_stdout_filename(salt):
    tail = md5(salt).hexdigest()
    return "/tmp/varnish-out-{0}".format(tail)


def _clean_vcl_file(instance_address):
    out = file(_rand_stdout_filename(instance_address), "w+")
    cmd = 'sudo bash -c \'echo "" > /etc/varnish/default.vcl\''
    exit_status = subprocess.call(["ssh", instance_address, "-l", "ubuntu", cmd], stdout=out, stderr=subprocess.STDOUT)
    out.seek(0)
    out = out.read()
    syslog.syslog(syslog.LOG_ERR, out)
    if exit_status != 0:
        raise Exception("Unable to clean vcl file from instance with ip {0}. Error was: {1}".format(instance_address, out))


def _update_vcl_file(instance_address, app_address):
    out = file(_rand_stdout_filename(instance_address), "w+")
    cmd = 'sudo bash -c "echo \'{0}\' > /etc/varnish/default.vcl && service varnish reload"'.format(vcl_template.format(app_address))
    exit_status = subprocess.call(["ssh", instance_address, "-l", "ubuntu", "-o", "StrictHostKeyChecking no", cmd], stdout=out, stderr=subprocess.STDOUT)
    out.seek(0)
    out = out.read()
    syslog.syslog(syslog.LOG_ERR, out)
    if exit_status != 0:
        syslog.syslog(syslog.LOG_ERR, "Unable to update vcl file from instance with ip {0}. Error was: {1}".format(instance_address, out))
        raise Exception("Caught problem while logging in in service VM. Please try again in a minute...")


def _delete_from_database(name):
    c = conn.cursor()
    c.execute("delete from instance_app where app_name=?", [name])
    conn.commit()


def _get_instance_id(service_instance):
    c = conn.cursor()
    query = "select instance_id from instance_app where app_name=? limit 1"
    c.execute(query, [service_instance])
    result = c.fetchall()
    if len(result) == 0 or len(result[0]) == 0:
        return ""
    return result[0][0]


def _delete_ec2_instance(instance_id):
    conn = _ec2_connection()
    return conn.terminate_instances(instance_ids=[instance_id])


def _create_ec2_instance():
    conn = _ec2_connection()
    key = open(key_path).read()
    user_data = """#cloud-config
ssh_authorized_keys: ['{0}']
""".format(key)
    reservation = None
    try:
        reservation = conn.run_instances(image_id=ami_id, subnet_id=subnet_id, user_data=user_data)
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, "Got error while creating EC2 instance:")
        syslog.syslog(syslog.LOG_ERR, e.message)
    return reservation


def _ec2_connection():
    from boto import ec2
    return ec2.connect_to_region(region, access_key, secret_key)


def _store_instance_and_app(reservation, app_name):
    instance_apps = []
    for i in reservation.instances:
        instance_apps.append((i.id, app_name))
    c = conn.cursor()
    c.executemany("insert into instance_app values (?, ?)", instance_apps)
    conn.commit()


def _get_database_name():
    if os.environ.get("DB_PATH"):  # this env var must be an absolute path
        return os.environ["DB_PATH"]
    return os.path.realpath(os.path.join(__file__, "../", default_db_name))


conn = sqlite3.connect(_get_database_name())
if __name__ == "__main__":
    api.run()
