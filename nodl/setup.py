from setuptools import find_packages, setup

package_name = 'nodl'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    package_data={
        package_name: ['resources/*.yaml', 'resources/fragments/*.yaml'],
    },
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/resources', ['nodl/resources/nodl.schema.yaml']),
        (
            'share/' + package_name + '/resources/fragments',
            [
                'nodl/resources/fragments/node.nodl.yaml',
                'nodl/resources/fragments/lifecycle_node.nodl.yaml',
            ],
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Emerson Knapp',
    maintainer_email='emerson@polymathrobotics.com',
    description='NoDL - Node Description Language library',
    license='Apache License 2.0',
    tests_require=['pytest'],
)
