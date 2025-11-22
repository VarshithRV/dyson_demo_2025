#!/usr/bin/env python3

import sys
from typing import List

import rclpy
from rclpy.node import Node

from example_interfaces.srv import Trigger
from ai_soft_touch_motion_planning_msgs.srv import Pick
from open_set_object_detection_msgs.srv import GetObjectLocations
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped

TEXT_PROMPT = "blue_circle.red_triangle.green_square"


class PerceptionAndPickClient(Node):
    def __init__(self):
        super().__init__("perception_and_pick_client")

        # ---------- Trigger (motion state) clients ----------
        self.right_preaction_client = self.create_client(
            Trigger, "/right_preaction_server/move_to_state"
        )

        # ---------- Perception client (RIGHT camera) ----------
        self.right_perception_client = self.create_client(
            GetObjectLocations, "right_get_object_locations"
        )

        # ---------- Pick client (RIGHT arm; rws by default) ----------
        # Change this to "/rws_pick_and_place_server/pick_and_place"
        # if you want to use the RWS end-effector.
        self.right_pick_client = self.create_client(
            Pick, "/rws_pick_and_place_server/pick_and_place"
        )

    # ------------------- Helper: Trigger call -------------------

    def _call_trigger(self, client, name: str) -> bool:
        self.get_logger().info(f"Waiting for {name} service...")
        if not client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(f"{name} service not available.")
            return False

        req = Trigger.Request()
        self.get_logger().info(f"Sending Trigger request to {name}")
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is not None:
            self.get_logger().info(f"{name} response: {future.result()}")
            return future.result().success
        else:
            self.get_logger().error(
                f"{name} service call failed: {future.exception()}"
            )
            return False

    # ------------------- Perception call -------------------

    def _make_perception_request(self, prompt_str: str) -> GetObjectLocations.Request:
        req = GetObjectLocations.Request()
        req.prompt = String()
        req.prompt.data = prompt_str
        return req

    def call_right_perception(self):
        service_name = "right_get_object_locations"
        self.get_logger().info(f"Waiting for {service_name}...")
        if not self.right_perception_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(f"{service_name} not available.")
            return None

        req = self._make_perception_request(TEXT_PROMPT)
        self.get_logger().info(f"Calling {service_name} with prompt '{TEXT_PROMPT}'")
        future = self.right_perception_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is None:
            self.get_logger().error(f"{service_name} call failed.")
            return None

        res = future.result()
        objects = list(res.result.object_position)  # List of ObjectPosition
        self._print_detected_objects(objects)
        return objects

    def _print_detected_objects(self, objects: List):
        self.get_logger().info(f"Detected {len(objects)} objects from right camera.")
        for i, obj in enumerate(objects):
            pose: PoseStamped = obj.pose
            p = pose.pose.position
            cls = getattr(obj, "Class", "")
            self.get_logger().info(
                f"[{i}] Class='{cls}', pos=({p.x:.3f}, {p.y:.3f}, {p.z:.3f})"
            )

    # ------------------- User selection -------------------

    def ask_user_for_indices(self, num_objects: int) -> List[int]:
        if num_objects == 0:
            return []

        print("\nSelect objects to pick.")
        print(" - Enter comma-separated indices (e.g. 0,2,3)")
        print(" - Or type 'all' to pick all detected objects")
        print(" - Or just press ENTER to abort\n")

        while True:
            user_input = input("Selection: ").strip()
            if user_input == "":
                print("No selection made. Aborting picking.")
                return []

            if user_input.lower() == "all":
                return list(range(num_objects))

            try:
                indices = [int(x.strip()) for x in user_input.split(",") if x.strip()]
                # Validate
                if all(0 <= idx < num_objects for idx in indices):
                    return indices
                else:
                    print(f"Invalid indices. Valid range is [0, {num_objects - 1}].")
            except ValueError:
                print("Could not parse input. Please enter indices like: 0,1,2 or 'all'.")

    # ------------------- Pick call -------------------

    def call_right_pick(self, obj, idx: int):
        service_name = "/rws_pick_and_place_server/pick_and_place"
        self.get_logger().info(f"Waiting for {service_name}...")
        if not self.right_pick_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(f"{service_name} not available.")
            return

        req = Pick.Request()

        pose: PoseStamped = obj.pose
        position = pose.pose.position
        req.object_position.x = position.x
        req.object_position.y = position.y
        req.object_position.z = position.z

        # Use object class as prompt (or any other string you want)
        cls = getattr(obj, "Class", "")
        req.prompt = cls if cls else "picked_object"

        # Use detection index as the request index
        req.index = idx

        self.get_logger().info(
            f"Sending Pick request for object {idx}: "
            f"class='{cls}', pos=({position.x:.3f}, {position.y:.3f}, {position.z:.3f})"
        )

        future = self.right_pick_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is not None:
            self.get_logger().info(f"Pick response (idx={idx}): {future.result()}")
        else:
            self.get_logger().error(
                f"Pick service failed for object {idx}: {future.exception()}"
            )

    # ------------------- Full workflow -------------------

    def run_workflow(self):
        # 1. Right arm preaction
        self.get_logger().info("=== Step 1: Right arm preaction ===")
        ok = self._call_trigger(
            self.right_preaction_client,
            "right_preaction_server/move_to_state",
        )
        if not ok:
            self.get_logger().error("Preaction failed. Aborting workflow.")
            return

        # 2. Right perception
        self.get_logger().info("=== Step 2: Right perception ===")
        objects = self.call_right_perception()
        if objects is None or len(objects) == 0:
            self.get_logger().warn("No objects detected. Aborting workflow.")
            return

        # 3. Ask user which objects to pick
        self.get_logger().info("=== Step 3: User selection of objects ===")
        indices = self.ask_user_for_indices(len(objects))
        if not indices:
            self.get_logger().info("No objects selected. Workflow complete.")
            return

        # 4. Pick & place each selected object with right arm
        self.get_logger().info("=== Step 4: Pick & place selected objects ===")
        for idx in indices:
            obj = objects[idx]
            self.call_right_pick(obj, idx)

        self.get_logger().info("Workflow finished.")


def main(args=None):
    rclpy.init(args=args)
    node = PerceptionAndPickClient()

    try:
        node.run_workflow()
    except KeyboardInterrupt:
        node.get_logger().info("Interrupted by user.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
