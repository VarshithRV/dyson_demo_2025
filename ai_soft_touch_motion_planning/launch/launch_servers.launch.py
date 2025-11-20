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

    rws_pick_and_place_server = Node(
    package="ai_soft_touch_motion_planning",
    executable="pick_and_place_server",
    name="rws_pick_and_place_server",
    output="screen",
    parameters=[
        robot_description_kinematics,
        {
            "planning_group": "right_ur16e",
            "place_x":0.085,
            "place_y":-0.482,
            "place_z":0.037,
            "orientation_w":0.001,
            "orientation_x":-0.488,
            "orientation_y":0.873,
            "orientation_z":0.006,
            "pick_offset_x":0.0,
            "pick_offset_y":0.0,
            "pick_offset_z":0.0,
            "look_offset_x":0.0,
            "look_offset_y":0.0,
            "look_offset_z":0.2,
            "height_of_movement":0.25,
        },
        ],
    )

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
            "shoulder_pan": 0.04691828027611484,
            "shoulder_lift": -1.1132075333272593,
            "elbow": -1.2901087525747499,
            "wrist_1": -2.3206509305199208,
            "wrist_2": 1.5723150119469158,
            "wrist_3": -0.6135582260386983,
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
            "shoulder_pan": 0.06231409038318228,
            "shoulder_lift": -1.386356573534534,
            "elbow": -1.9287975938281376,
            "wrist_1": -1.3997576476930407,
            "wrist_2": 1.5822272848798489,
            "wrist_3": 0.6144593569871353,
        },
        ],
    )

    return LaunchDescription([
        rws_pick_and_place_server,
        left_preaction_server,
        right_preaction_server,
        left_rest_server,
        right_rest_server,
        ])