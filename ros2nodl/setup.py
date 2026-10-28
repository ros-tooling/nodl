# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
import xml.etree.ElementTree as ET
from pathlib import Path

from setuptools import find_packages, setup

package_name = 'ros2nodl'

setup(
    name=package_name,
    version=ET.parse(Path(__file__).with_name('package.xml')).findtext('version'),
    packages=find_packages(exclude=['test', 'test.*']),
    # colcon uses test extras to select pytest instead of unittest.
    extras_require={'test': ['pytest', 'pyright']},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    entry_points={
        'ros2cli.command': [
            'nodl = ros2nodl.command.nodl:NodlCommand',
        ],
        'ros2cli.extension_point': [
            'ros2nodl.verb = ros2nodl.verb:VerbExtension',
        ],
        'ros2nodl.verb': [
            'conform = ros2nodl.verb.conform:ConformVerb',
            'describe = ros2nodl.verb.describe:DescribeVerb',
            'diff = ros2nodl.verb.diff:DiffVerb',
            'rewrite = ros2nodl.verb.rewrite:RewriteVerb',
            'validate = ros2nodl.verb.validate:ValidateVerb',
        ],
    },
)
