# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import argparse

from feaas import api
from feaas.runners import instance_scalator


def run(manager):
    parser = argparse.ArgumentParser("Instance scalator runner")
    parser.add_argument("-i", "--interval",
                        help="Interval for running InstanceTerminator (in seconds)",
                        default=10, type=int)
    args = parser.parse_args()
    scalator = instance_scalator.InstanceScalator(manager, args.interval)
    scalator.loop()

if __name__ == "__main__":
    manager = api.get_manager()
    run(manager)
