# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import json
import os

from flask import Flask, request

from . import storage

api = Flask(__name__)


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
    return "null", 201


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
        return json.dumps(manager.info(name)), 200
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


def get_manager():
    pass

if __name__ == "__main__":
    api.run()
