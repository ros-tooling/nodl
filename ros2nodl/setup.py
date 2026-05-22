# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from setuptools import find_packages, setup

package_name = 'ros2nodl'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    extras_require={'test': ['pytest']},
    zip_safe=True,
    entry_points={
        'ros2cli.command': [
            'nodl = ros2nodl.command.nodl:NodlCommand',
        ],
        'ros2cli.extension_point': [
            'ros2nodl.verb = ros2nodl.verb:VerbExtension',
        ],
        'ros2nodl.verb': [
            'validate = ros2nodl.verb.validate:ValidateVerb',
        ],
    },
)
