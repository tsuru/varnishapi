# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import json


class Instance(object):

    def __init__(self, name=None, dns_name=None, id=None):
        self.name = name
        self.dns_name = dns_name
        self.id = id

    def to_json(self):
        return json.dumps(self.to_dict())

    def to_dict(self):
        return {"name": self.name, "dns_name": self.dns_name,
                "id": self.id}
