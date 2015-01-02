# -*- coding: utf-8 -*-

# Copyright 2014 varnishapi authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.
import codecs

from setuptools import setup, find_packages

from feaas import __version__

README = codecs.open('README.rst', encoding='utf-8').read()

setup(
    name="tsuru-feaas",
    url="https://github.com/tsuru/varnishapi",
    version=__version__,
    description="Frontend as-a-service API for Tsuru PaaS",
    long_description=README,
    author="Tsuru",
    author_email="tsuru@corp.globo.com",
    classifiers=[
        "Programming Language :: Python :: 2.7",
    ],
    packages=find_packages(exclude=["docs", "tests", "samples"]),
    include_package_data=True,
    install_requires=["Flask==0.9", "boto==2.25.0", "pymongo==2.6.3",
                      "python-varnish==0.2.1", "httplib2==0.9"],
)
