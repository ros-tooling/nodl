# Changelog

## [3.0.0](https://github.com/ros-tooling/nodl/compare/2.0.3...3.0.0) (2026-11-12)


### ⚠ BREAKING CHANGES

* `on_*` lifecycle methods in node implementations will cause a compile error because they are `final` in the new base class. Need to be renamed to `handle_*` with the same signature, and omit calling base class method.
* **nodl_generator_py:** install generated modules as nodl_generated.<package> ([#258](https://github.com/ros-tooling/nodl/issues/258))

### Features

* add nodl_runtime_cpp with LifecycleNode wrapper ([#290](https://github.com/ros-tooling/nodl/issues/290)) ([03c3b49](https://github.com/ros-tooling/nodl/commit/03c3b491e829d2491a61bf8edaa1fe83bf915e23))
* add nodl_runtime_py for the runtime dependencies of generated Python code ([#237](https://github.com/ros-tooling/nodl/issues/237)) ([2857e97](https://github.com/ros-tooling/nodl/commit/2857e971321f3d74314f0935a7c7bbb0368974f7))
* **nodl_generator_cpp:** add NODE role with namespace support ([#195](https://github.com/ros-tooling/nodl/issues/195)) ([8e253fb](https://github.com/ros-tooling/nodl/commit/8e253fbce5a2297ad7315ebbefcf17a109d68f29))
* **nodl_generator_cpp:** allow producing shared libraries ([#192](https://github.com/ros-tooling/nodl/issues/192)) ([3f7503d](https://github.com/ros-tooling/nodl/commit/3f7503d7619177493e581fcf0cb2d77551e4341c))
* **nodl_generator_cpp:** export generated libraries as CMake targets with EXPORT ([#194](https://github.com/ros-tooling/nodl/issues/194)) ([1a1b613](https://github.com/ros-tooling/nodl/commit/1a1b61312da56b3993e0558fefe30276033bdc67))
* **nodl_generator_cpp:** follow BUILD_SHARED_LIBS for the default library type ([#215](https://github.com/ros-tooling/nodl/issues/215)) ([1d0b1fe](https://github.com/ros-tooling/nodl/commit/1d0b1fe3ed30c5ca2c9f15c09e75553a94615d69))
* **nodl_generator_cpp:** generate C++ headers under a package include prefix ([#193](https://github.com/ros-tooling/nodl/issues/193)) ([c0121b7](https://github.com/ros-tooling/nodl/commit/c0121b76824ce9d498748e56b87b2611ffc932e9))
* **nodl_generator_cpp:** generate lifecycle publishers for lifecycle bases ([#196](https://github.com/ros-tooling/nodl/issues/196)) ([1cec813](https://github.com/ros-tooling/nodl/commit/1cec813fb6520a1eac7b0cf65d7571d91f7a37b6))
* **nodl_generator_py:** install generated modules as nodl_generated.&lt;package&gt; ([#258](https://github.com/ros-tooling/nodl/issues/258)) ([11cb6ca](https://github.com/ros-tooling/nodl/commit/11cb6caf16cc0103053bbdc8c0698351c08e7bf5)), closes [#257](https://github.com/ros-tooling/nodl/issues/257)
* **nodl_generator_py:** register ament_python documents in the ament index ([#248](https://github.com/ros-tooling/nodl/issues/248)) ([7f5c4a5](https://github.com/ros-tooling/nodl/commit/7f5c4a52bc326db61f4d1ffb6ffa520517bd15f1)), closes [#253](https://github.com/ros-tooling/nodl/issues/253)
* **nodl_generator_py:** support colcon --symlink-install for ament_python packages ([#249](https://github.com/ros-tooling/nodl/issues/249)) ([bac6683](https://github.com/ros-tooling/nodl/commit/bac668399914ac9f3df636702958863e82145db9)), closes [#254](https://github.com/ros-tooling/nodl/issues/254)
* register generated node documents with the ament index ([#200](https://github.com/ros-tooling/nodl/issues/200)) ([f601077](https://github.com/ros-tooling/nodl/commit/f6010773b29fd87095a592486cdedc5b762ad1d7))
* **ros2nodl:** add a pytest helper for conformance tests ([#246](https://github.com/ros-tooling/nodl/issues/246)) ([633f35a](https://github.com/ros-tooling/nodl/commit/633f35a514d29fcc8a21c181cf08701ff73efbbe)), closes [#256](https://github.com/ros-tooling/nodl/issues/256)
* **ros2nodl:** add check mode to ros2nodl rewrite ([#201](https://github.com/ros-tooling/nodl/issues/201)) ([f0fdf9a](https://github.com/ros-tooling/nodl/commit/f0fdf9ade4a30f354bf1fab04364c8be7af510ec))
* **ros2nodl:** ignore rules for conformance checks ([#216](https://github.com/ros-tooling/nodl/issues/216)) ([cd56cb6](https://github.com/ros-tooling/nodl/commit/cd56cb6449191265a431fcd7a889a33535a0dd93))


### Bug Fixes

* **ament_nodl:** allow nodl_add_conformance_test to be called more than once ([#217](https://github.com/ros-tooling/nodl/issues/217)) ([cf8c1ad](https://github.com/ros-tooling/nodl/commit/cf8c1adfdaee7854e9358d661292d40c4e988317))
* **ament_nodl:** fail at configure time for unregistered local includes ([#205](https://github.com/ros-tooling/nodl/issues/205)) ([4acaf9a](https://github.com/ros-tooling/nodl/commit/4acaf9a820c96ff06d6e38c4bc8b56c73d794815))
* **ament_nodl:** finalize ament_nodl registrations once per project ([#203](https://github.com/ros-tooling/nodl/issues/203)) ([88788ae](https://github.com/ros-tooling/nodl/commit/88788aedf6ca15a72809ca3d9be06afb7cb6db82))
* **ament_nodl:** name installed share copies after the resource ([#204](https://github.com/ros-tooling/nodl/issues/204)) ([01f6482](https://github.com/ros-tooling/nodl/commit/01f64829e03ba585a6441c1d7b78900a328dba33))
* **ament_nodl:** reject duplicate resource names and files in ament_nodl_register ([#190](https://github.com/ros-tooling/nodl/issues/190)) ([f93fa52](https://github.com/ros-tooling/nodl/commit/f93fa527a49b62c21134f40586cf39b523cac799))
* generators carry the nodl_common_interfaces dependency ([#239](https://github.com/ros-tooling/nodl/issues/239)) ([60adf89](https://github.com/ros-tooling/nodl/commit/60adf890ea66c1d870e24a79914200310c977a41))
* **nodl_generator_py:** export generate_parameter_library_py to generating packages ([#235](https://github.com/ros-tooling/nodl/issues/235)) ([2e7fe73](https://github.com/ros-tooling/nodl/commit/2e7fe7355464fb85859eb1060b6cddddf8b0ecdf))
* reject Python provider roles on root documents ([#223](https://github.com/ros-tooling/nodl/issues/223)) ([f8d0b8a](https://github.com/ros-tooling/nodl/commit/f8d0b8a3babbbc7e81ac690704130b25ef2d7ba7))
