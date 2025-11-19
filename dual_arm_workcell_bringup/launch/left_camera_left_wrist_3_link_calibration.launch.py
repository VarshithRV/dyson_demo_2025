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
                "0.0264557",
                "--y",
                "-0.0720002",
                "--z",
                "-0.00195138",
                "--qx",
                "0.480826",
                "--qy",
                "-0.511275",
                "--qz",
                "0.514343",
                "--qw",
                "0.492804",
                # "--roll",
                # "1.55599",
                # "--pitch",
                # "-0.00929775",
                # "--yaw",
                # "1.62272",
            ],
        ),
    ]
    return LaunchDescription(nodes)
