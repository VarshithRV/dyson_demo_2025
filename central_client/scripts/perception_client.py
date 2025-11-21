#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from open_set_object_detection_msgs.srv import GetObjectLocations
from geometry_msgs.msg import PoseStamped

import cv2
import cv_bridge


TEXT_PROMPT = "blue_circle.red_triangle.green_square"


class GetObjectLocationsClient(Node):
    def __init__(self):
        super().__init__("get_object_locations_client")

        self.bridge = cv_bridge.CvBridge()

        # Create clients for both services
        self.left_client = self.create_client(
            GetObjectLocations, "left_get_object_locations"
        )
        self.right_client = self.create_client(
            GetObjectLocations, "right_get_object_locations"
        )

        # Wait for services
        self.get_logger().info("Waiting for left_get_object_locations...")
        self.left_client.wait_for_service()
        self.get_logger().info("Waiting for right_get_object_locations...")
        self.right_client.wait_for_service()

        self.get_logger().info("Both services available. Calling now...")

        # Call both services once, sequentially
        self.call_both_services()

        # After done, shutdown
        self.get_logger().info("Done. Shutting down node.")
        rclpy.shutdown()

    def make_request(self, prompt_str: str) -> GetObjectLocations.Request:
        req = GetObjectLocations.Request()
        req.prompt = String()
        req.prompt.data = prompt_str
        return req

    def call_service_sync(self, client, name: str, prompt: str):
        req = self.make_request(prompt)
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is None:
            self.get_logger().error(f"Service call to {name} failed.")
            return None

        self.get_logger().info(f"Service {name} returned a result.")
        return future.result()

    def display_result(self, result, window_name: str):
        if result is None:
            return

        positions = result.result.object_position
        image_msg = result.result.image

        # Convert image and display
        try:
            img = self.bridge.imgmsg_to_cv2(image_msg, desired_encoding="bgr8")
            cv2.imshow(window_name, img)
        except Exception as e:
            self.get_logger().error(f"Failed to convert/show image: {e}")
            img = None

        # Print positions
        self.get_logger().info(f"Detected {len(positions)} objects for {window_name}")
        for i, obj in enumerate(positions):
            pose: PoseStamped = obj.pose
            p = pose.pose.position
            self.get_logger().info(
                f"[{window_name}] Object {i}: "
                f"Class='{obj.Class}', "
                f"pos = ({p.x:.3f}, {p.y:.3f}, {p.z:.3f})"
            )
            # Optional: wait for key between objects
            if img is not None:
                cv2.setWindowTitle(window_name, f"{window_name} - Obj {i}: {obj.Class}")
                cv2.imshow(window_name, img)
                cv2.waitKey(500)  # 0.5s per object; set to 0 to wait for keypress

        # Final wait before closing this window
        if img is not None:
            self.get_logger().info(f"Press any key in the '{window_name}' window to continue...")
            cv2.waitKey(0)
            cv2.destroyWindow(window_name)

    def call_both_services(self):
        # LEFT
        left_res = self.call_service_sync(
            self.left_client, "left_get_object_locations", TEXT_PROMPT
        )
        self.display_result(left_res, "Left Camera Result")

        # RIGHT
        right_res = self.call_service_sync(
            self.right_client, "right_get_object_locations", TEXT_PROMPT
        )
        self.display_result(right_res, "Right Camera Result")


def main(args=None):
    rclpy.init(args=args)
    client_node = GetObjectLocationsClient()
    # Node shuts itself down after both calls


if __name__ == "__main__":
    main()
