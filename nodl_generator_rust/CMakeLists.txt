cmake_minimum_required(VERSION 3.16)
project(nodl_generator_rust)

find_package(ament_cmake REQUIRED)

install(PROGRAMS scripts/nodl_generate_rust
  DESTINATION lib/${PROJECT_NAME})

install(FILES cmake/nodl_generate_rust.cmake
  DESTINATION share/${PROJECT_NAME}/cmake)

install(DIRECTORY nodl_generator_rust/templates
  DESTINATION share/${PROJECT_NAME}/templates)

ament_package(CONFIG_EXTRAS "nodl_generator_rust-extras.cmake.in")
