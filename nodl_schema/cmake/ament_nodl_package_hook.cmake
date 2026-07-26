# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# ament_package() extension hook for ament_nodl.
#
# Collects all NoDL filenames accumulated by ament_nodl_install() calls
# and registers them as a single ``nodl_interfaces`` ament index resource.
#
get_property(_nodl_filenames GLOBAL PROPERTY _AMENT_NODL_INTERFACE_FILENAMES)
if(_nodl_filenames)
  list(REMOVE_DUPLICATES _nodl_filenames)
  list(JOIN _nodl_filenames "\n" _content)
  string(APPEND _content "\n")
  ament_index_register_resource(nodl_interfaces
    CONTENT "${_content}")
endif()
