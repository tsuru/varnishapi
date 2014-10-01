# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import codecs
import httplib2
import os

import varnish
from feaas import storage

VCL_TEMPLATE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                                 "misc", "default.vcl"))

DUMP_VCL_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                             "misc", "dump_vcls.bash"))


class BaseManager(object):

    def __init__(self, storage):
        self.storage = storage

    def new_instance(self, name):
        self._check_duplicate(name)
        instance = storage.Instance(name)
        self.storage.store_instance(instance)
        return instance

    def _check_duplicate(self, name):
        try:
            self.storage.retrieve_instance(name=name)
            raise storage.InstanceAlreadyExistsError()
        except storage.InstanceNotFoundError:
            pass

    def bind(self, name, app_host):
        instance = self.storage.retrieve_instance(name=name)
        bind = storage.Bind(app_host, instance)
        self.storage.store_bind(bind)

    def unbind(self, name, app_host):
        instance = self.storage.retrieve_instance(name=name)
        for unit in instance.units:
            self.remove_vcl(unit.dns_name, unit.secret)
        bind = storage.Bind(app_host, instance)
        self.storage.remove_bind(bind)

    def write_vcl(self, instance_addr, secret, app_addr):
        vcl = self.vcl_template() % {"app_host": app_addr}
        try:
            handler = varnish.VarnishHandler("{0}:6082".format(instance_addr),
                                             secret=secret)
            handler.vcl_inline("feaas", vcl.encode("iso-8859-1", "ignore"))
            handler.vcl_use("feaas")
            handler.quit()
        except AssertionError as e:
            if len(e.args) > 0 and "106 Already a VCL program named" in e.args[0]:
                return
            raise e

    def remove_vcl(self, instance_addr, secret):
        handler = varnish.VarnishHandler("{0}:6082".format(instance_addr),
                                         secret=secret)
        handler.vcl_use("boot")
        handler.vcl_discard("feaas")
        handler.quit()

    def vcl_template(self):
        with codecs.open(VCL_TEMPLATE_FILE, encoding="utf-8") as f:
            content = f.read()
            content = content.replace("\n", " ")
            content = content.replace('"', r'\"')
            content = content.replace("\t", "")
            return '"%s"' % content.strip()

    def remove_instance(self, name):
        instance = self.storage.retrieve_instance(name=name)
        instance.state = "removed"
        self.storage.store_instance(instance)

    def info(self, name):
        instance = self.storage.retrieve_instance(name=name)
        return [{"label": "Address",
                 "value": instance.units[0].dns_name}]

    def status(self, name):
        instance = self.storage.retrieve_instance(name=name)
        return instance.state

    def scale_instance(self, name, quantity):
        if quantity < 1:
            raise ValueError("quantity must be a positive integer")
        instance = self.storage.retrieve_instance(name=name)
        if instance.state == "scaling":
            raise ValueError("instance is already scaling")
        if quantity == len(instance.units):
            raise ValueError("instance already have %d units" % quantity)
        self.storage.store_scale_job({"instance": name, "quantity": quantity,
                                      "state": "pending"})

    def get_user_data(self, secret):
        if "USER_DATA_URL" in os.environ:
            url = os.environ.get("USER_DATA_URL")
            h = httplib2.Http()
            _, user_data = h.request(url)
            return user_data.replace("VARNISH_SECRET_KEY", secret)
        user_data_lines = None
        packages = os.environ.get("API_PACKAGES")
        if packages:
            user_data_lines = ["apt-get update",
                               "apt-get install -y {0}".format(packages),
                               "sed -i -e 's/-T localhost:6082/-T :6082/' /etc/default/varnish",
                               "sed -i -e 's/-a :6081/-a :8080/' /etc/default/varnish",
                               "echo {0} > /etc/varnish/secret".format(secret),
                               "service varnish restart",
                               "cat > /etc/cron.hourly/dump_vcls <<'END'",
                               open(DUMP_VCL_FILE).read(),
                               "END",
                               "chmod +x /etc/cron.hourly/dump_vcls"]
        if user_data_lines:
            return "\n".join(user_data_lines) + "\n"

    def start_instance(self, name):
        raise NotImplementedError()

    def terminate_instance(self, name):
        raise NotImplementedError()

    def physical_scale(self, instance, quantity):
        raise NotImplementedError()
