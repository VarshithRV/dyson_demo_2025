""" Static transform publisher acquired via MoveIt 2 hand-eye calibration """
""" EYE-IN-HAND: left_wrist_3_link -> left_camera_link """
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    nodes = [
        Node(
            package="tf2_ros",
            executable="static_transform_publisher",
            output="log",
            arguments=[
                "--frame-id",
                "left_wrist_3_link",
                "--child-frame-id",
                "left_camera_link",
                "--x",
                "-0.0117627",
                "--y",
                "-0.101001",
                "--z",
                "0.0271018",
                "--qx",
                "-0.501211",
                "--qy",
                "0.516289",
                "--qz",
                "-0.491037",
                "--qw",
                "-0.491036",
                # "--roll",
                # "1.60634",
                # "--pitch",
                # "-0.0148073",
                # "--yaw",
                # "1.58614",
            ],
        ),
    ]
    return LaunchDescription(nodes)
