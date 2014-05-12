# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import argparse

from feaas import api, vcl_writer


def run(storage):
    parser = argparse.ArgumentParser("VCL Writer runner")
    parser.add_argument("-i", "--interval",
                        help="Interval for running VCLWriter (in seconds)",
                        default=10, type=int)
    parser.add_argument("-n", "--max-items",
                        help="Maximum number of units to process at a time",
                        type=int)
    args = parser.parse_args()
    writer = vcl_writer.VCLWriter(storage, args.interval, args.max_items)
    writer.loop()

if __name__ == "__main__":
    manager = api.get_manager()
    run(manager.storage)
