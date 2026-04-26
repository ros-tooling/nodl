from setuptools import find_packages, setup

package_name = 'ros2nodl'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Emerson Knapp',
    maintainer_email='emerson@polymathrobotics.com',
    description='ros2cli plugin providing the nodl command',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'ros2cli.command': [
            'nodl = ros2nodl.command.nodl:NodlCommand',
        ],
        'ros2cli.extension_point': [
            'ros2nodl.verb = ros2nodl.verb:VerbExtension',
        ],
        'ros2nodl.verb': [
            'validate = ros2nodl.verb.validate:ValidateVerb',
            'describe = ros2nodl.verb.describe:DescribeVerb',
        ],
    },
)
