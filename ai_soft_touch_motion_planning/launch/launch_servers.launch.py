from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os
import yaml
import xacro


def generate_launch_description():

    robot_description_kinematics = {
    "robot_description_kinematics": {
        "left_ur16e": {
            "kinematics_solver": "kdl_kinematics_plugin/KDLKinematicsPlugin",
            "kinematics_solver_attempts": 3,
            "kinematics_solver_search_resolution": 0.005,
            "kinematics_solver_timeout": 0.005,},
        "right_ur16e": {
            "kinematics_solver": "kdl_kinematics_plugin/KDLKinematicsPlugin",
            "kinematics_solver_attempts": 3,
            "kinematics_solver_search_resolution": 0.005,
            "kinematics_solver_timeout": 0.005,}
    }}

    left_preaction_server = Node(
    package="ai_soft_touch_motion_planning",
    executable="predefined_state_server",
    name="left_preaction_server",
    output="screen",
    parameters=[
        robot_description_kinematics,
        {
            "planning_group": "left_ur16e",
            "shoulder_pan": 0.0,
            "shoulder_lift": 0.0,
            "elbow": 0.0,
            "wrist_1": 0.0,
            "wrist_2": 0.0,
            "wrist_3": 0.0,
        },
        ],
    )

    right_preaction_server = Node(
    package="ai_soft_touch_motion_planning",
    executable="predefined_state_server",
    name="right_preaction_server",
    output="screen",
    parameters=[
        robot_description_kinematics,
        {
            "planning_group": "right_ur16e",
            "shoulder_pan": 0.0,
            "shoulder_lift": 0.0,
            "elbow": 0.0,
            "wrist_1": 0.0,
            "wrist_2": 0.0,
            "wrist_3": 0.0,
        },
        ],
    )

    left_rest_server = Node(
    package="ai_soft_touch_motion_planning",
    executable="predefined_state_server",
    name="left_rest_server",
    output="screen",
    parameters=[
        robot_description_kinematics,
        {
            "planning_group": "left_ur16e",
            "shoulder_pan": 0.0,
            "shoulder_lift": -1.57,
            "elbow": 0.0,
            "wrist_1": -1.57,
            "wrist_2": 0.0,
            "wrist_3": 0.0,
        },
        ],
    )

    right_rest_server = Node(
    package="ai_soft_touch_motion_planning",
    executable="predefined_state_server",
    name="right_rest_server",
    output="screen",
    parameters=[
        robot_description_kinematics,
        {
            "planning_group": "right_ur16e",
            "shoulder_pan": 0.0,
            "shoulder_lift": -1.57,
            "elbow": 0.0,
            "wrist_1": -1.57,
            "wrist_2": 0.0,
            "wrist_3": 0.0,
        },
        ],
    )

    return LaunchDescription([
        left_preaction_server,
        right_preaction_server,
        left_rest_server,
        right_rest_server,
        ])