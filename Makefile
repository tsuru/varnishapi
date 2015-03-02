# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

test_deps:
	pip install -qr test_requirements.txt

test: test_deps
	python -m unittest discover

run:
	python run.py

coverage: test_deps
	coverage run --source=. -m unittest discover
	coverage report -m --omit=test\*,setup\*,run\*
	rm .coverage

flake8:
	flake8 --ignore=E731 --max-line-length=99 .
