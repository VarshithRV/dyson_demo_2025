#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

from ai_soft_touch_motion_planning_msgs.srv import Pick
from example_interfaces.srv import Trigger


class SimpleClient(Node):
    def __init__(self):
        super().__init__("simple_pick_and_rest_client")

        # Pick services
        self.suction_pick_client = self.create_client(
            Pick, "/suction_pick_and_place_server/pick_and_place"
        )
        self.rws_pick_client = self.create_client(
            Pick, "/rws_pick_and_place_server/pick_and_place"
        )

        # Trigger services
        self.left_rest_client = self.create_client(
            Trigger, "/left_rest_server/move_to_state"
        )
        self.right_rest_client = self.create_client(
            Trigger, "/right_rest_server/move_to_state"
        )
        self.right_preaction_client = self.create_client(
            Trigger, "/right_preaction_server/move_to_state"
        )
        self.left_preaction_client = self.create_client(
            Trigger, "/left_preaction_server/move_to_state"
        )

    # ------------------- Pick services -------------------

    def call_suction_pick(self):
        self.get_logger().info("Waiting for suction Pick service...")
        self.suction_pick_client.wait_for_service()

        req = Pick.Request()
        req.object_position.x = 0.348
        req.object_position.y = -0.002
        req.object_position.z = 0.03
        req.prompt = "hello"
        req.index = 1

        self.get_logger().info(f"Sending suction Pick request: {req}")
        future = self.suction_pick_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is not None:
            self.get_logger().info(f"Suction Pick response: {future.result()}")
        else:
            self.get_logger().error(
                f"Suction Pick service failed: {future.exception()}"
            )

    def call_rws_pick(self):
        self.get_logger().info("Waiting for RWS Pick service...")
        self.rws_pick_client.wait_for_service()

        req = Pick.Request()
        req.object_position.x = 0.348
        req.object_position.y = -0.002
        req.object_position.z = 0.03
        req.prompt = "hello"
        req.index = 1

        self.get_logger().info(f"Sending RWS Pick request: {req}")
        future = self.rws_pick_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is not None:
            self.get_logger().info(f"RWS Pick response: {future.result()}")
        else:
            self.get_logger().error(
                f"RWS Pick service failed: {future.exception()}"
            )

    # ------------------- Trigger services -------------------

    def _call_trigger_client(self, client, name: str):
        self.get_logger().info(f"Waiting for {name} service...")
        client.wait_for_service()

        req = Trigger.Request()
        self.get_logger().info(f"Sending Trigger request to {name}")
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is not None:
            self.get_logger().info(f"{name} response: {future.result()}")
        else:
            self.get_logger().error(
                f"{name} service failed: {future.exception()}"
            )

    def call_left_rest(self):
        self._call_trigger_client(self.left_rest_client, "left_rest_server/move_to_state")

    def call_right_rest(self):
        self._call_trigger_client(self.right_rest_client, "right_rest_server/move_to_state")

    def call_right_preaction(self):
        self._call_trigger_client(self.right_preaction_client, "right_preaction_server/move_to_state")

    def call_left_preaction(self):
        self._call_trigger_client(self.left_preaction_client, "left_preaction_server/move_to_state")


def main():
    rclpy.init()
    node = SimpleClient()

    # Trigger services
    node.call_left_rest()
    node.call_right_rest()
    node.call_right_preaction()
    node.call_left_preaction()
    
    # Pick services
    node.call_suction_pick()
    node.call_left_preaction()
    node.call_rws_pick()
    node.call_right_preaction()


    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
