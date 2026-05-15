cmake_minimum_required(VERSION 3.16)
project(nodl_generator_cpp)

find_package(ament_cmake REQUIRED)

install(
  PROGRAMS scripts/nodl_generate_cpp
  DESTINATION lib/${PROJECT_NAME}
)

install(
  DIRECTORY templates/
  DESTINATION share/${PROJECT_NAME}/templates
)

install(
  FILES cmake/nodl_generate_cpp.cmake
  DESTINATION share/${PROJECT_NAME}/cmake
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_generator test/test_generator.py)
endif()

ament_package(
  CONFIG_EXTRAS "nodl_generator_cpp-extras.cmake.in"
)
