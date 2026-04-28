from setuptools import setup

package_name = "nodl_schema"

setup(
    name=package_name,
    version="0.0.0",
    packages=[package_name, package_name + ".schemas"],
    package_data={package_name + ".schemas": ["*.yaml"]},
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            "share/" + package_name + "/schemas",
            [
                package_name + "/schemas/nodl.schema.yaml",
                package_name + "/schemas/parameter.schema.yaml",
            ],
        ),
    ],
    install_requires=["setuptools", "pyyaml", "jsonschema"],
    zip_safe=True,
    maintainer="Alistair English",
    maintainer_email="hello@alistairenglish.com",
    description="NoDL schema definitions and validator.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "nodl-validate = nodl_schema.validator:main",
        ],
    },
)
