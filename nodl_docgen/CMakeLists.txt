cmake_minimum_required(VERSION 3.16)
project(nodl_docgen)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Install the Python package so 'nodl_docgen.sphinx_ext' is importable.
ament_python_install_package(${PROJECT_NAME})

# Install the CLI script.
install(PROGRAMS scripts/nodl_docgen
  DESTINATION lib/nodl_docgen)

# Install the cmake macro file.
install(FILES cmake/nodl_docgen.cmake
  DESTINATION share/${PROJECT_NAME}/cmake)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_generator test/test_generator.py)
  ament_add_pytest_test(test_cli test/test_cli.py)
  ament_add_pytest_test(test_sphinx_ext test/test_sphinx_ext.py)
endif()

ament_package(CONFIG_EXTRAS "nodl_docgen-extras.cmake.in")
