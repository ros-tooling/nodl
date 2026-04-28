from setuptools import setup

package_name = "ros2nodl"

setup(
    name=package_name,
    version="0.0.0",
    packages=[
        package_name,
        package_name + ".command",
        package_name + ".verb",
    ],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools", "pyyaml", "nodl_schema", "ros2cli"],
    zip_safe=True,
    maintainer="Alistair English",
    maintainer_email="hello@alistairenglish.com",
    description="The ros2 command-line interface for NoDL.",
    license="Apache-2.0",
    entry_points={
        "ros2cli.command": [
            "nodl = ros2nodl.command.nodl:NodlCommand",
        ],
        "ros2cli.extension_point": [
            "ros2nodl.verb = ros2nodl.verb:VerbExtension",
        ],
        "ros2nodl.verb": [
            "validate = ros2nodl.verb.validate:ValidateVerb",
        ],
    },
)
