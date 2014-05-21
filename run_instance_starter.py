# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import argparse

from feaas import api, instance_starter


def run(manager):
    parser = argparse.ArgumentParser("Instance starter runner")
    parser.add_argument("-i", "--interval",
                        help="Interval for running InstanceStarter (in seconds)",
                        default=10, type=int)
    args = parser.parse_args()
    starter = instance_starter.InstanceStarter(manager, args.interval)

if __name__ == "__main__":
    manager = api.get_manager()
    run(manager)
