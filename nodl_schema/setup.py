# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
from setuptools import setup

package_name = 'nodl_schema'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    package_data={package_name: ['schemas/*.yaml', 'schemas/fragments/*.yaml']},
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
        (
            'share/' + package_name + '/schemas/fragments',
            [
                'nodl_schema/schemas/fragments/node.nodl.yaml',
                'nodl_schema/schemas/fragments/lifecycle_node.nodl.yaml',
            ],
        ),
    ],
    zip_safe=True,
    extras_require={'test': ['pytest']},
)
