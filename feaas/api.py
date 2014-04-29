# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import json
import os

from flask import Flask, Response, request

from . import storage
from .managers import ec2

api = Flask(__name__)
api.debug = os.environ.get("API_DEBUG", "0") in ("True", "true", "1")

managers = {
    "ec2": ec2.EC2Manager,
}


@api.route("/resources", methods=["POST"])
def create_instance():
    name = request.form.get("name")
    if not name:
        return "name is required", 400
    manager = get_manager()
    manager.add_instance(name)
    return "", 201


@api.route("/resources/<name>", methods=["DELETE"])
def remove_instance(name):
    manager = get_manager()
    try:
        manager.remove_instance(name)
    except storage.InstanceNotFoundError:
        return "Instance not found", 404
    return "", 200


@api.route("/resources/<name>", methods=["POST"])
def bind(name):
    app_host = request.form.get("app-host")
    if not app_host:
        return "app-host is required", 400
    manager = get_manager()
    try:
        manager.bind(name, app_host)
    except storage.InstanceNotFoundError:
        return "Instance not found", 404
    return Response(response="null", status=201,
                    mimetype="application/json")


@api.route("/resources/<name>/hostname/<host>", methods=["DELETE"])
def unbind(name, host):
    manager = get_manager()
    try:
        manager.unbind(name, host)
    except storage.InstanceNotFoundError:
        return "Instance not found", 404
    return "", 200


@api.route("/resources/<name>", methods=["GET"])
def info(name):
    manager = get_manager()
    try:
        info = manager.info(name)
        if "secret" in info:
            del info["secret"]
        return Response(response=json.dumps(info), status=200,
                        mimetype="application/json")
    except storage.InstanceNotFoundError:
        return "Instance not found", 404


@api.route("/resources/<name>/status", methods=["GET"])
def status(name):
    states = {"running": 204, "pending": 202}
    manager = get_manager()
    try:
        status = manager.status(name)
    except storage.InstanceNotFoundError:
        return "Instance not found", 404
    return "", states.get(status, 500)


@api.route("/resources/<name>/scale", methods=["POST"])
def scale_instance(name):
    quantity = request.form.get("quantity")
    if not quantity:
        return "missing quantity", 400
    manager = get_manager()
    try:
        manager.scale_instance(name, int(quantity))
    except ValueError:
        return "invalid quantity: %s" % quantity, 400
    except storage.InstanceNotFoundError:
        return "Instance not found", 404
    return "", 201


def register_manager(name, obj, override=False):
    if not override and name in managers:
        raise ValueError("Manager already registered")
    managers[name] = obj


def get_manager():
    manager = os.environ.get("API_MANAGER", "ec2")
    manager_class = managers.get(manager)
    if not manager_class:
        raise ValueError("{0} is not a valid manager".format(manager))
    mongodb_uri = os.environ.get("API_MONGODB_URI")
    mongodb_database = os.environ.get("API_MONGODB_DATABASE_NAME")
    return manager_class(storage.MongoDBStorage(mongo_uri=mongodb_uri,
                                                dbname=mongodb_database))
