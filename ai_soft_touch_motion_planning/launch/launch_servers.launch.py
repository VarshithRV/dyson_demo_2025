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
            "place_x":0.217,
            "place_y":0.469,
            "place_z":0.040,
            "orientation_w":0.0,
            "orientation_x":0.0,
            "orientation_y":1.0,
            "orientation_z":0.0,
            "pick_offset_x":0.0,
            "pick_offset_y":0.0,
            "pick_offset_z":0.0,
            "look_offset_x":0.0,
            "look_offset_y":0.0,
            "look_offset_z":0.2,
            "place_step_x":0.05,
            "place_step_y":0.05,
            "height_of_movement":0.25,
            "endeffector_link": "right_tool0",
            "pin_out1":14,
            "pin_out2":15,
            "arm_side":"right"
        },
        {"use_sim_time":True},
        ],
    )

    suction_pick_and_place_server = Node(
    package="ai_soft_touch_motion_planning",
    executable="pick_and_place_ft_feedback_server",
    name="suction_pick_and_place_server",
    output="screen",
    parameters=[
        robot_description_kinematics,
        {
            "planning_group": "left_ur16e",
            "place_x":0.217,
            "place_y":0.469,
            "place_z":0.040,
            "orientation_w":0.0,
            "orientation_x":0.0,
            "orientation_y":1.0,
            "orientation_z":0.0,
            "pick_offset_x":0.0,
            "pick_offset_y":0.0,
            "pick_offset_z":0.0,
            "look_offset_x":0.0,
            "look_offset_y":0.0,
            "look_offset_z":0.2,
            "place_step_x":0.05,
            "place_step_y":0.05,
            "height_of_movement":0.25,
            "endeffector_link": "left_tool0",
            "pin_out1":12,
            "pin_out2":0,
            "arm_side":"left",
            "ft_threshold": 5.0,
        },
        {"use_sim_time":True},
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
            "shoulder_pan": 0.04691828027611484,
            "shoulder_lift": -1.1132075333272593,
            "elbow": -1.2901087525747499,
            "wrist_1": -2.3206509305199208,
            "wrist_2": 1.5723150119469158,
            "wrist_3": -0.6135582260386983,
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
            "shoulder_pan": 0.06231409038318228,
            "shoulder_lift": -1.386356573534534,
            "elbow": -1.9287975938281376,
            "wrist_1": -1.3997576476930407,
            "wrist_2": 1.5822272848798489,
            "wrist_3": 0.6144593569871353,
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
        suction_pick_and_place_server,
        left_preaction_server,
        right_preaction_server,
        left_rest_server,
        right_rest_server,
        ])