cmake_minimum_required(VERSION 3.16)
project(test_nodl_generator_cpp)

find_package(ament_cmake REQUIRED)
find_package(nodl_generator_cpp REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)

# Generate the base class from the NoDL file
nodl_generate_cpp(test_node nodl/test_node.nodl.yaml)
target_include_directories(test_node SYSTEM PUBLIC ${std_msgs_INCLUDE_DIRS})
target_link_libraries(test_node PUBLIC ${std_msgs_LIBRARIES})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(test_generated_node test/test_generated_node.cpp)
  target_link_libraries(test_generated_node test_node)
endif()

ament_package()
