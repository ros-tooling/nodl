nodl
====

``nodl`` is a metapackage for the ROS 2 Node Definition Language (NoDL) project.
It includes the common NoDL packages as dependencies, without providing any functionality of its own.

NoDL describes a node's ROS interface -- its parameters, topics, services, actions -- as a declarative schema-validated document.
That declaration can then be used to generate documentation, boilerplate code, testing, and more.

The full project documentation, including the concepts, the schema reference and the tutorials, is published at
`nodl.readthedocs.io <https://nodl.readthedocs.io/en/latest/>`_.

Packages
--------

Each package has its own specific documentation.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Package
     - Description
   * - `nodl_schema <../nodl_schema/>`_
     - The NoDL schema, in-memory model, and validation.
   * - `nodl_observe <../nodl_observe/>`_
     - Observes a running node and reports its runtime interface.
   * - `ros2nodl <../ros2nodl/>`_
     - The ``ros2 nodl`` command line.
   * - `ament_nodl <../ament_nodl/>`_
     - CMake macros for registering NoDL documents, creating related build and test targets.
   * - `nodl_common_interfaces <../nodl_common_interfaces/>`_
     - NoDL descriptions of the standard ROS 2 node base classes.
   * - `nodl_generator_cpp <../nodl_generator_cpp/>`_
     - Generates an ``rclcpp`` base-node class from a NoDL document.
   * - `nodl_docgen <../nodl_docgen/>`_
     - Renders NoDL documents into a package's Sphinx documentation.
   * - `nodl_conformance <../nodl_conformance/>`_
     - Compares two NoDL documents for semantic conformance.

Source
------

`github.com/ros-tooling/nodl <https://github.com/ros-tooling/nodl>`_

.. This replaces the index rosdoc2 generates, so the pages it also generates are listed here.
.. toctree::
   :maxdepth: 1

   Standard Documents <standards>
