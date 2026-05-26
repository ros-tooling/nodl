cmake_minimum_required(VERSION 3.16)
project(test_nodl_generator_cpp)

find_package(ament_cmake REQUIRED)
find_package(nodl_generator_cpp REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(example_interfaces REQUIRED)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)

  # --- pub/sub axis ---------------------------------------------------------
  # See plan_cpp_tests.md for the per-axis layout (fixture / derived / test).
  nodl_generate_cpp(pubsub_node fixtures/pubsub_node.nodl.yaml)
  target_include_directories(pubsub_node SYSTEM PUBLIC ${std_msgs_INCLUDE_DIRS})
  target_link_libraries(pubsub_node PUBLIC ${std_msgs_LIBRARIES})

  add_library(pubsub_node_derived derived/pubsub_node_derived.cpp)
  target_include_directories(pubsub_node_derived PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/derived)
  target_link_libraries(pubsub_node_derived PUBLIC pubsub_node)

  ament_add_gtest(test_pubsub test/test_pubsub.cpp)
  target_link_libraries(test_pubsub pubsub_node_derived)

  # --- service axis ---------------------------------------------------------
  nodl_generate_cpp(service_node fixtures/service_node.nodl.yaml)
  target_include_directories(service_node SYSTEM PUBLIC ${example_interfaces_INCLUDE_DIRS})
  target_link_libraries(service_node PUBLIC ${example_interfaces_LIBRARIES})

  add_library(service_node_derived derived/service_node_derived.cpp)
  target_include_directories(service_node_derived PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/derived)
  target_link_libraries(service_node_derived PUBLIC service_node)

  ament_add_gtest(test_service test/test_service.cpp)
  target_link_libraries(test_service service_node_derived)

  # --- params axis ----------------------------------------------------------
  nodl_generate_cpp(params_node fixtures/params_node.nodl.yaml)

  add_library(params_node_derived INTERFACE)
  target_include_directories(params_node_derived INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/derived)
  target_link_libraries(params_node_derived INTERFACE params_node)

  ament_add_gtest(test_params test/test_params.cpp)
  target_link_libraries(test_params params_node_derived)

  # --- lifecycle axis -------------------------------------------------------
  nodl_generate_cpp(lifecycle_pubsub_node fixtures/lifecycle_pubsub_node.nodl.yaml LIFECYCLE)
  target_include_directories(lifecycle_pubsub_node SYSTEM PUBLIC ${std_msgs_INCLUDE_DIRS})
  target_link_libraries(lifecycle_pubsub_node PUBLIC ${std_msgs_LIBRARIES})

  add_library(lifecycle_pubsub_node_derived derived/lifecycle_pubsub_node_derived.cpp)
  target_include_directories(lifecycle_pubsub_node_derived PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/derived)
  target_link_libraries(lifecycle_pubsub_node_derived PUBLIC lifecycle_pubsub_node)

  ament_add_gtest(test_lifecycle_pubsub test/test_lifecycle_pubsub.cpp)
  target_link_libraries(test_lifecycle_pubsub lifecycle_pubsub_node_derived)
endif()

ament_package()
