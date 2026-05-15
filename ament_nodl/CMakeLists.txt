cmake_minimum_required(VERSION 3.16)
project(ament_nodl)

find_package(ament_cmake REQUIRED)

install(FILES
  cmake/ament_nodl_register_fragment.cmake
  cmake/ament_nodl_register_node.cmake
  DESTINATION share/${PROJECT_NAME}/cmake)

install(FILES resource/ament_nodl
  DESTINATION share/ament_index/resource_index/packages)
install(FILES package.xml
  DESTINATION share/${PROJECT_NAME})

ament_package(CONFIG_EXTRAS "ament_nodl-extras.cmake.in")
