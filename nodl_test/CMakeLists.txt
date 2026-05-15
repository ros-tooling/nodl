cmake_minimum_required(VERSION 3.16)
project(nodl_test)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(FILES cmake/nodl_add_test.cmake
  DESTINATION share/${PROJECT_NAME}/cmake)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_compare test/test_compare.py)
endif()

ament_package(CONFIG_EXTRAS "nodl_test-extras.cmake.in")
