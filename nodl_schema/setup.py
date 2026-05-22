from setuptools import setup

package_name = "nodl_schema"

setup(
    name=package_name,
    version="0.0.0",
    packages=[package_name],
    package_data={package_name: ["schemas/*.yaml"]},
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            "share/" + package_name + "/schemas",
            [
                "nodl_schema/schemas/nodl.schema.yaml",
                "nodl_schema/schemas/parameter.schema.yaml",
            ],
        ),
    ],
    zip_safe=True,
)
