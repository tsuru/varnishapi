#!/bin/bash

# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

function dump_vcl() {
        vcl_name=$1
	file=/etc/varnish/${vcl_name}.vcl
        if [ -f $file ]
        then
                mv ${file} ${file}.old
        fi
        varnishadm vcl.show ${vcl_name} > $file
}

vcls=`varnishadm vcl.list | grep -v 200 | awk '{print $3}'`
for vcl in $vcls
do
        dump_vcl $vcl
done

active_vcl=`varnishadm vcl.list | grep -v 200 | grep ^active | awk '{print $3}'`
if [ -h /etc/varnish/default.vcl ]
then
	rm /etc/varnish/default.vcl
else
	mv /etc/varnish/default.vcl /etc/varnish/default.vcl.old
fi
ln -s /etc/varnish/${active_vcl}.vcl /etc/varnish/default.vcl
