""" Static transform publisher acquired via MoveIt 2 hand-eye calibration """
""" EYE-IN-HAND: right_wrist_3_link -> right_camera_link """
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
                "right_wrist_3_link",
                "--child-frame-id",
                "right_camera_link",
                "--x",
                "-0.0940388",
                "--y",
                "-0.0615407",
                "--z",
                "0.0316184",
                "--qx",
                "0.282472",
                "--qy",
                "-0.655436",
                "--qz",
                "0.268079",
                "--qw",
                "0.647107",
                # "--roll",
                # "1.59697",
                # "--pitch",
                # "-0.770961",
                # "--yaw",
                # "1.57487",
            ],
        ),
    ]
    return LaunchDescription(nodes)
