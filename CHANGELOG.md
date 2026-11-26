# Changelog

## [3.0.0](https://github.com/ros-tooling/nodl/compare/2.0.3...3.0.0) (2026-11-26)


### ⚠ BREAKING CHANGES

* **python:** the service clients and action clients of generated Python lifecycle nodes are `Gated` members. Replace `self.cli_x.call_async(req)` with `if (client := self.cli_x.get()) is not None: client.call_async(req)`.
* **python:** the service servers of generated Python lifecycle nodes exist only while the node is active, and are not discoverable until it activates.
* **python:** the subscriptions of generated Python lifecycle nodes exist only while the node is active, and the node has no subscriptions in the graph until it activates.
* **nodl_runtime_py:** generated Python lifecycle bases derive `nodl_runtime_py.lifecycle.LifecycleNode`. Authors define `handle_*` hooks instead of overriding `on_*`.
* **cpp:** the service clients and action clients of generated lifecycle nodes are `Gated` members. Replace `cli_x_->call(...)` with `if (auto client = cli_x_.get()) { client->call(...); }`.
* **cpp:** the service servers of generated lifecycle nodes exist only while the node is active, and are not discoverable until it activates.
* **cpp:** the subscriptions of generated lifecycle nodes are `Managed` members that exist only while the node is active, and the node has no subscriptions in the graph until it activates.
* `on_*` lifecycle methods in node implementations will cause a compile error because they are `final` in the new base class. Need to be renamed to `handle_*` with the same signature, and omit calling base class method.
* **nodl_generator_py:** install generated modules as nodl_generated.<package> ([#258](https://github.com/ros-tooling/nodl/issues/258))

### Features

* add nodl_runtime_cpp with LifecycleNode wrapper ([#290](https://github.com/ros-tooling/nodl/issues/290)) ([03c3b49](https://github.com/ros-tooling/nodl/commit/03c3b491e829d2491a61bf8edaa1fe83bf915e23))
* add nodl_runtime_py for the runtime dependencies of generated Python code ([#237](https://github.com/ros-tooling/nodl/issues/237)) ([2857e97](https://github.com/ros-tooling/nodl/commit/2857e971321f3d74314f0935a7c7bbb0368974f7))
* **cpp:** create service servers of generated C++ lifecycle nodes on activation ([#305](https://github.com/ros-tooling/nodl/issues/305)) ([bf786dd](https://github.com/ros-tooling/nodl/commit/bf786dd778dd0ff86e2e0f94bfd382e2947ffe88))
* **cpp:** hand out service and action clients of generated C++ lifecycle nodes only while active ([#307](https://github.com/ros-tooling/nodl/issues/307)) ([c5fcb9e](https://github.com/ros-tooling/nodl/commit/c5fcb9ebbfcc22ffd705a3d2c214c5fd0c4ca8d2))
* **cpp:** manage C++ lifecycle subscriptions ([#292](https://github.com/ros-tooling/nodl/issues/292)) ([8b0d5a0](https://github.com/ros-tooling/nodl/commit/8b0d5a0c7525fca92aefc930c02374bfdcdbd0c6))
* **nodl_generator_cpp:** add NODE role with namespace support ([#195](https://github.com/ros-tooling/nodl/issues/195)) ([8e253fb](https://github.com/ros-tooling/nodl/commit/8e253fbce5a2297ad7315ebbefcf17a109d68f29))
* **nodl_generator_cpp:** allow producing shared libraries ([#192](https://github.com/ros-tooling/nodl/issues/192)) ([3f7503d](https://github.com/ros-tooling/nodl/commit/3f7503d7619177493e581fcf0cb2d77551e4341c))
* **nodl_generator_cpp:** configure callback groups from metadata ([#287](https://github.com/ros-tooling/nodl/issues/287)) ([5f50654](https://github.com/ros-tooling/nodl/commit/5f506545b914024430df77006fb26e03980e515a))
* **nodl_generator_cpp:** export generated libraries as CMake targets with EXPORT ([#194](https://github.com/ros-tooling/nodl/issues/194)) ([1a1b613](https://github.com/ros-tooling/nodl/commit/1a1b61312da56b3993e0558fefe30276033bdc67))
* **nodl_generator_cpp:** follow BUILD_SHARED_LIBS for the default library type ([#215](https://github.com/ros-tooling/nodl/issues/215)) ([1d0b1fe](https://github.com/ros-tooling/nodl/commit/1d0b1fe3ed30c5ca2c9f15c09e75553a94615d69))
* **nodl_generator_cpp:** generate C++ headers under a package include prefix ([#193](https://github.com/ros-tooling/nodl/issues/193)) ([c0121b7](https://github.com/ros-tooling/nodl/commit/c0121b76824ce9d498748e56b87b2611ffc932e9))
* **nodl_generator_cpp:** generate lifecycle publishers for lifecycle bases ([#196](https://github.com/ros-tooling/nodl/issues/196)) ([1cec813](https://github.com/ros-tooling/nodl/commit/1cec813fb6520a1eac7b0cf65d7571d91f7a37b6))
* **nodl_generator_py:** install generated modules as nodl_generated.&lt;package&gt; ([#258](https://github.com/ros-tooling/nodl/issues/258)) ([11cb6ca](https://github.com/ros-tooling/nodl/commit/11cb6caf16cc0103053bbdc8c0698351c08e7bf5)), closes [#257](https://github.com/ros-tooling/nodl/issues/257)
* **nodl_generator_py:** register ament_python documents in the ament index ([#248](https://github.com/ros-tooling/nodl/issues/248)) ([7f5c4a5](https://github.com/ros-tooling/nodl/commit/7f5c4a52bc326db61f4d1ffb6ffa520517bd15f1)), closes [#253](https://github.com/ros-tooling/nodl/issues/253)
* **nodl_generator_py:** support colcon --symlink-install for ament_python packages ([#249](https://github.com/ros-tooling/nodl/issues/249)) ([bac6683](https://github.com/ros-tooling/nodl/commit/bac668399914ac9f3df636702958863e82145db9)), closes [#254](https://github.com/ros-tooling/nodl/issues/254)
* **nodl_runtime_cpp:** add Gated, an entity handed out only while the node is active ([#306](https://github.com/ros-tooling/nodl/issues/306)) ([761142d](https://github.com/ros-tooling/nodl/commit/761142dd81df92904ff7fcd9af495181dad8e17d))
* **nodl_runtime_py:** add Gated, an entity handed out only while the node is active ([#316](https://github.com/ros-tooling/nodl/issues/316)) ([de8ccc6](https://github.com/ros-tooling/nodl/commit/de8ccc6548780dbd369f598e8eeea28fe0080d03))
* **nodl_runtime_py:** add LifecycleNode with sealed transitions and handle_* hooks ([#312](https://github.com/ros-tooling/nodl/issues/312)) ([6496f45](https://github.com/ros-tooling/nodl/commit/6496f4540298225975e78a0bd91b77fc3b5e9130))
* **nodl_runtime_py:** create endpoints on activation with an activation registry and Managed ([#313](https://github.com/ros-tooling/nodl/issues/313)) ([cb713d5](https://github.com/ros-tooling/nodl/commit/cb713d5cdb66851b30ef89248d0f6641602e777b))
* **python:** create service servers of generated Python lifecycle nodes on activation ([#315](https://github.com/ros-tooling/nodl/issues/315)) ([6b2f20d](https://github.com/ros-tooling/nodl/commit/6b2f20ddf577928dc5d5b85b03af9b0dfc527e9e))
* **python:** create subscriptions of generated Python lifecycle nodes on activation ([#314](https://github.com/ros-tooling/nodl/issues/314)) ([491a3cf](https://github.com/ros-tooling/nodl/commit/491a3cf1825e18bddd35d221b6c5e7db259ff4dc))
* **python:** hand out service and action clients of generated Python lifecycle nodes only while active ([#317](https://github.com/ros-tooling/nodl/issues/317)) ([4820d4c](https://github.com/ros-tooling/nodl/commit/4820d4cde25404ed8f59d84cfde2791ed7390983))
* register generated node documents with the ament index ([#200](https://github.com/ros-tooling/nodl/issues/200)) ([f601077](https://github.com/ros-tooling/nodl/commit/f6010773b29fd87095a592486cdedc5b762ad1d7))
* **ros2nodl:** add a pytest helper for conformance tests ([#246](https://github.com/ros-tooling/nodl/issues/246)) ([633f35a](https://github.com/ros-tooling/nodl/commit/633f35a514d29fcc8a21c181cf08701ff73efbbe)), closes [#256](https://github.com/ros-tooling/nodl/issues/256)
* **ros2nodl:** add check mode to ros2nodl rewrite ([#201](https://github.com/ros-tooling/nodl/issues/201)) ([f0fdf9a](https://github.com/ros-tooling/nodl/commit/f0fdf9ade4a30f354bf1fab04364c8be7af510ec))
* **ros2nodl:** configure and activate lifecycle nodes in conformance tests ([#304](https://github.com/ros-tooling/nodl/issues/304)) ([c2290f9](https://github.com/ros-tooling/nodl/commit/c2290f97bd00d35668d00367c8723937e0ad5daa))
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
* **ros2nodl:** retry conformance while expected endpoints are still being discovered ([#322](https://github.com/ros-tooling/nodl/issues/322)) ([5ed59d8](https://github.com/ros-tooling/nodl/commit/5ed59d8d776af00147779f42682510e36a47bee8))
