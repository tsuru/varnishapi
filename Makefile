# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

test_deps:
	pip install -qr test_requirements.txt

test: test_deps
	python -m unittest discover