^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Changelog for package ros2nodl
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

2.0.0 (2026-09-01)
------------------
* Add NoDL conformance comparison and conform verb (`#115 <https://github.com/ros-tooling/nodl/issues/115>`_)
* feat: ament_nodl_register rewrite local refs to ament index refs (`#111 <https://github.com/ros-tooling/nodl/issues/111>`_)
* feat: remove nodl_schema CLI entrypoint, always use ros2nodl for CLIs (`#112 <https://github.com/ros-tooling/nodl/issues/112>`_)
* feat: Include resolvers always return a Path (`#110 <https://github.com/ros-tooling/nodl/issues/110>`_)
* test: add pyright checker for nodl_schema and ros2nodl (`#109 <https://github.com/ros-tooling/nodl/issues/109>`_)
* Include: groundwork with ament_index only (`#97 <https://github.com/ros-tooling/nodl/issues/97>`_)
* Add byte-array parameter type to NoDL schema (`#95 <https://github.com/ros-tooling/nodl/issues/95>`_)
* Add ros2 nodl describe: rosgraph_msgs/Node -> NoDL document (`#53 <https://github.com/ros-tooling/nodl/issues/53>`_) (`#89 <https://github.com/ros-tooling/nodl/issues/89>`_)
* Per-package documentation (`#87 <https://github.com/ros-tooling/nodl/issues/87>`_)
* feat: Observe a running node as rosgraph_msgs/Node via ros2 nodl describe (`#83 <https://github.com/ros-tooling/nodl/issues/83>`_)
* create new nodl v2 schema within a new package named nodl (`#55 <https://github.com/ros-tooling/nodl/issues/55>`_)
* start fresh (`#54 <https://github.com/ros-tooling/nodl/issues/54>`_)
* Using underscore names in `setup.cfg` (`#42 <https://github.com/ros-tooling/nodl/issues/42>`_)
* Contributors: Abrar Rahman Protyasha, Alistair English, Emerson Knapp, Luke Sy

0.3.1 (2020-11-19)
------------------
* Merge pull request `#40 <https://github.com/ros-tooling/nodl/issues/40>`_ from Arnatious/bump_version
  Bump version to 0.3.1
* 0.3.1
* Merge pull request `#39 <https://github.com/ros-tooling/nodl/issues/39>`_ from ubuntu-robotics/foxy_merge
  merge foxy-devel changes back into master
* merge foxy-devel changes back into master
* Merge pull request `#35 <https://github.com/ros-tooling/nodl/issues/35>`_ from ubuntu-robotics/relicense-apache
  relicense project as Apache 2.0
* relicense project as Apache 2.0
* Merge pull request `#21 <https://github.com/ros-tooling/nodl/issues/21>`_ from Arnatious/add_direction
  add role field, replacing bool pairs
* add directionality flag
* Merge pull request `#23 <https://github.com/ros-tooling/nodl/issues/23>`_ from Arnatious/remove_qos
  strip qos from nodl_python
* Merge pull request `#22 <https://github.com/ros-tooling/nodl/issues/22>`_ from Arnatious/codecov
  test all packages and use codecov
* strip qos from nodl_python
* add codecov and rewrite ci script
* Contributors: Ted Kern

0.1.0 (2020-06-01)
------------------
* Merge pull request `#19 <https://github.com/ros-tooling/nodl/issues/19>`_ from kyrofa/bugfix/argcomplete_dep
  Depend on python3-argcomplete
* Depend on python3-argcomplete
  `argcomplete` is not a valid rosdep dependency.
* Merge pull request `#18 <https://github.com/ros-tooling/nodl/issues/18>`_ from ubuntu-robotics/bugfix/remove_buildtool_depend
  Remove buildtool_depend on nodl_python
* Remove buildtool_depend on nodl_python
  It's not a valid rosdep dependency and is unnecessary anyway.
* Update CHANGELOGs and package.xmls for 0.1.0
* Update CHANGELOGs and package.xmls for 0.1.0
* Merge pull request `#17 <https://github.com/ros-tooling/nodl/issues/17>`_ from Arnatious/update_readmes_and_tests
  Update readmes and tests
* fix license files, small print error in validate, readmes
* Merge pull request `#9 <https://github.com/ros-tooling/nodl/issues/9>`_ from Arnatious/cli
  add CLI with `show` and `validate` verbs
* add show and validate verbs
* Contributors: Kyle Fazzari, Ted Kern
