# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from glob import glob

from setuptools import setup

package_name = 'nodl_schema'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    package_data={package_name: ['schemas/*.yaml', 'schemas/bases/*.yaml']},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Globbed so new schema files are picked up automatically.
        ('share/' + package_name + '/schemas', glob('nodl_schema/schemas/*.yaml')),
        ('share/' + package_name + '/schemas/bases', glob('nodl_schema/schemas/bases/*.yaml')),
    ],
    zip_safe=True,
    extras_require={'test': ['pytest']},
)
