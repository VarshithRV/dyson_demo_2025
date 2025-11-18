import os
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess,
                            RegisterEventHandler)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    Command,
    FindExecutable,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue
from moveit_configs_utils import MoveItConfigsBuilder


def load_yaml(package_name, file_path):
    package_path = get_package_share_directory(package_name)
    absolute_file_path = os.path.join(package_path, file_path)

    try:
        with open(absolute_file_path) as file:
            return yaml.safe_load(file)
    except OSError:  # parent of IOError, OSError *and* WindowsError where available
        return None


def generate_launch_description():

    declared_launch_arguments = []
    declared_launch_arguments.append(
        DeclareLaunchArgument(
            "launch_servo",
            default_value="true",
            description="Launch Servo?",
        )
    )

    launch_servo = LaunchConfiguration("launch_servo")

    # Build MoveIt config (kinematics, pipelines, joint limits, etc.)
    moveit_config = MoveItConfigsBuilder(
        "dual_arm_workcell", package_name="dual_arm_workcell_moveit_config"
    ).to_moveit_configs()

    # ----------------------------------------------------------------------
    # Robot description from *description* package (overrides MoveItConfig URDF)
    # ----------------------------------------------------------------------
    robot_description_xacro = PathJoinSubstitution(
        [
            FindPackageShare("dual_arm_workcell_description"),
            "urdf",
            "dual_arm_workcell.urdf.xacro",  # adjust filename/path if needed
        ]
    )

    robot_description = {
        "robot_description": ParameterValue(
            Command(
                [
                    FindExecutable(name="xacro"),
                    " ",
                    robot_description_xacro,
                ]
            ),
            value_type=str,
        )
    }

    move_group_configuration = {
        "publish_robot_description_semantic": True,
        "publish_robot_description": True,
        "allow_trajectory_execution": True,
        "publish_planning_scene": True,
        "publish_geometry_updates": True,
        "publish_state_updates": True,
        "publish_transforms_updates": True,
    }

    # Order matters: later dicts override earlier ones.
    move_group_params = [
        moveit_config.to_dict(),
        robot_description,  # <-- this overrides robot_description from moveit_config
        move_group_configuration,
    ]

    move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        parameters=move_group_params,
        additional_env={"DISPLAY": ":0"},
    )

    rviz_config_file = PathJoinSubstitution(
        [FindPackageShare("dual_arm_workcell_moveit_config"), "config", "moveit.rviz"]
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2_moveit",
        output="log",
        arguments=["-d", rviz_config_file],
        parameters=[
            robot_description,  # use description-package URDF here
            moveit_config.robot_description_semantic,
            moveit_config.robot_description_kinematics,
            moveit_config.planning_pipelines,
            moveit_config.joint_limits,
        ],
    )

    # Servo node for realtime control (left)
    left_servo_yaml = load_yaml(
        "dual_arm_workcell_moveit_config", "config/left_ur_servo.yaml"
    )
    left_servo_params = {"moveit_servo": left_servo_yaml}
    left_servo_node = Node(
        package="moveit_servo",
        condition=IfCondition(launch_servo),
        executable="servo_node_main",
        name="left_servo_node",
        parameters=[
            left_servo_params,
            robot_description,  # use description-package URDF
            moveit_config.robot_description_semantic,
        ],
        output="screen",
    )

    # Servo node for realtime control (right)
    right_servo_yaml = load_yaml(
        "dual_arm_workcell_moveit_config", "config/right_ur_servo.yaml"
    )
    right_servo_params = {"moveit_servo": right_servo_yaml}
    right_servo_node = Node(
        package="moveit_servo",
        condition=IfCondition(launch_servo),
        executable="servo_node_main",
        name="right_servo_node",
        parameters=[
            right_servo_params,
            robot_description,  # use description-package URDF
            moveit_config.robot_description_semantic,
        ],
        output="screen",
    )

    return LaunchDescription(
        declared_launch_arguments
        + [
            move_group_node,
            left_servo_node,
            right_servo_node,
            rviz_node,
        ]
    )
