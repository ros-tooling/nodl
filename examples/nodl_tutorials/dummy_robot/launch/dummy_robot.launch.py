# SPDX-FileCopyrightText: 2018 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Launch the Dummy robot with a conventional, generated, or regressed laser."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import FileContent, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def _selected(name):
    return IfCondition(PythonExpression(["'", LaunchConfiguration('interface'), "' == '", name, "'"]))


def generate_launch_description():
    bringup = Path(get_package_share_directory('dummy_robot_bringup'))
    tutorial = Path(get_package_share_directory('nodl_tutorial_dummy_robot'))
    robot_description = FileContent(str(bringup / 'launch' / 'single_rrbot.urdf'))

    return LaunchDescription([
        DeclareLaunchArgument('interface', default_value='nodl'),
        DeclareLaunchArgument('scan_topic', default_value='scan'),
        DeclareLaunchArgument('scan_type', default_value='laser_scan'),
        DeclareLaunchArgument('scan_reliability', default_value='reliable'),
        DeclareLaunchArgument('scan_durability', default_value='volatile'),
        DeclareLaunchArgument('scan_history', default_value='keep_last'),
        DeclareLaunchArgument('scan_depth', default_value='10'),
        DeclareLaunchArgument('rviz', default_value='true'),
        Node(package='dummy_map_server', executable='dummy_map_server', output='screen'),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}],
        ),
        Node(package='dummy_sensors', executable='dummy_joint_states', output='screen'),
        Node(
            package='dummy_sensors',
            executable='dummy_laser',
            output='screen',
            condition=_selected('conventional'),
        ),
        Node(
            package='nodl_tutorial_dummy_robot',
            executable='dummy_laser_nodl',
            output='screen',
            condition=_selected('nodl'),
            remappings=[('scan', LaunchConfiguration('scan_topic'))],
        ),
        Node(
            package='nodl_tutorial_dummy_robot',
            executable='dummy_laser_regression',
            output='screen',
            condition=_selected('regression'),
            arguments=[
                LaunchConfiguration('scan_topic'),
                LaunchConfiguration('scan_type'),
                LaunchConfiguration('scan_reliability'),
                LaunchConfiguration('scan_durability'),
                LaunchConfiguration('scan_history'),
                LaunchConfiguration('scan_depth'),
            ],
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', str(tutorial / 'rviz' / 'dummy_robot.rviz')],
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ])
