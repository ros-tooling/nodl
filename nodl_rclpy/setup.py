from setuptools import find_packages, setup

package_name = 'nodl_rclpy'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/nodl_rclpy']),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='Emerson Knapp',
    maintainer_email='emerson@polymathrobotics.com',
    description='NoDL runtime base node for Python rclpy nodes.',
    license='Apache License 2.0',
    entry_points={},
)
