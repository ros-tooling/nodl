cmake_minimum_required(VERSION 3.16)
project(nodl_rclrs)

find_package(ament_cmake REQUIRED)
find_package(ament_cargo REQUIRED)

ament_cargo_build_package()

ament_package()
