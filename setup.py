# -*- coding: utf-8 -*-

import setuptools

from inventree_brother.version import BROTHER_PLUGIN_VERSION

with open('README.md', encoding='utf-8') as f:
    long_description = f.read()


setuptools.setup(
    name="inventree-brother-label-plugin",

    version=BROTHER_PLUGIN_VERSION,

    author="Dean Gardiner",

    author_email="me@dgardiner.net",

    description="Brother label printer plugin for InvenTree",

    long_description=long_description,

    long_description_content_type='text/markdown',

    keywords="inventree label printer printing inventory",

    url="https://github.com/fuzeman/inventree-brother-label-plugin",

    license="MIT",

    packages=setuptools.find_packages(),

    install_requires=[
        'brother-ql-inventree',
    ],

    setup_requires=[
        "wheel",
        "twine",
    ],

    python_requires=">=3.9",

    entry_points={
        "inventree_plugins": [
            "BrotherLabeLPlugin = inventree_brother.brother_plugin:BrotherLabelPlugin"
        ]
    },
)
