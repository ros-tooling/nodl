#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 EMPTY_WORKSPACE"
  exit 2
fi

tutorial_workspace=$1
script_directory=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repository_root=$(cd "${script_directory}/.." && pwd)

if [[ -d "${tutorial_workspace}" ]] && [[ -n "$(find "${tutorial_workspace}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "workspace is not empty: ${tutorial_workspace}"
  exit 2
fi

mkdir -p "${tutorial_workspace}/src"
ln -s "${repository_root}" "${tutorial_workspace}/src/nodl"
vcs import "${tutorial_workspace}/src" < "${script_directory}/ros2_demos.lock.repos"

rosdep install \
  --from-paths "${tutorial_workspace}/src" \
  --ignore-src \
  --rosdistro "${ROS_DISTRO:?source a ROS environment before running this script}" \
  --yes

colcon build \
  --base-paths "${tutorial_workspace}/src" \
  --packages-up-to \
    nodl_tutorial_verification \
    demo_nodes_cpp \
    demo_nodes_py \
    dummy_robot_bringup

echo "workspace built: ${tutorial_workspace}"
echo "source ${tutorial_workspace}/install/setup.bash"
