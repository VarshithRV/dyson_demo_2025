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
    executable="pick_and_place_local_perception_server",
    name="rws_pick_and_place_server",
    output="screen",
    parameters=[
        robot_description_kinematics,
        {
            "planning_group": "right_ur16e",
            "place_x":0.161,
            "place_y":0.637,
            "place_z":0.038,
            "orientation_w":0.038,
            "orientation_x":0.369,
            "orientation_y":0.927,
            "orientation_z":-0.057,
            "pick_offset_x":0.0,
            "pick_offset_y":0.015,
            "pick_offset_z":0.020,
            "look_offset_x":0.0,
            "look_offset_y":0.08,
            "look_offset_z":0.45,
            "place_step_x":0.05,
            "place_step_y":0.05,
            "height_of_movement":0.25,
            "endeffector_link": "right_tool0",
            "pin_out1":14,
            "pin_out2":0,
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
            "place_x":0.161,
            "place_y":0.637,
            "place_z":0.038,
            "orientation_w":0.038,
            "orientation_x":0.369,
            "orientation_y":0.927,
            "orientation_z":-0.057,
            "pick_offset_x":0.0,
            "pick_offset_y":0.0,
            "pick_offset_z":0.0,
            "look_offset_x":0.0,
            "look_offset_y":0.0,
            "look_offset_z":0.45,
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
            "shoulder_pan": -2.370838467274801,
            "shoulder_lift": -1.3852829945138474,
            "elbow": 0.8208854834185999,
            "wrist_1": -0.9787348669818421,
            "wrist_2": -1.577686611806051,
            "wrist_3": 0.7582406997680664,
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
            "shoulder_pan": -0.6716254393206995,
            "shoulder_lift": -1.4663793754628678,
            "elbow": -0.945048451423645,
            "wrist_1": -2.2198287449278773,
            "wrist_2": 1.6617790460586548,
            "wrist_3": 0.09304250776767731,
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
                "shoulder_pan": -3.7407785097705286,
                "shoulder_lift": -1.8669382534422816,
                "elbow": 2.030813995991842,
                "wrist_1": -1.609297891656393,
                "wrist_2": -1.2706669012652796,
                "wrist_3": -1.3307812849627894,
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
                "shoulder_pan": 0.5529513359069824,
                "shoulder_lift": -1.1297608476928254,
                "elbow": -2.2185397148132324,
                "wrist_1": -1.0740774732879181,
                "wrist_2": 1.1414644718170166,
                "wrist_3": 2.0575029850006104,
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