# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import xml.etree.ElementTree as ET
from pathlib import Path

from setuptools import find_packages, setup

package_name = 'nodl_schema'

setup(
    name=package_name,
    version=ET.parse(Path(__file__).with_name('package.xml')).findtext('version'),
    packages=find_packages(exclude=['test', 'test.*']),
    package_data={package_name: ['schemas/*.yaml']},
    # colcon uses test extras to select pytest instead of unittest.
    extras_require={'test': ['pytest', 'pyright']},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (
            'share/' + package_name + '/schemas',
            [
                'nodl_schema/schemas/nodl.schema.yaml',
                'nodl_schema/schemas/parameter.schema.yaml',
            ],
        ),
    ],
)
