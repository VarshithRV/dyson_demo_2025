#!/usr/bin/env python3

import sys
from typing import List, Dict, Any

import rclpy
from rclpy.node import Node

from example_interfaces.srv import Trigger
from ai_soft_touch_motion_planning_msgs.srv import Pick
from open_set_object_detection_msgs.srv import GetObjectLocations
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped

import cv2
from cv_bridge import CvBridge
import base64
import json

from openai import OpenAI


# Prompt used for the perception server (shapes to detect)
# TEXT_PROMPT = "blue_circle,red_hex,green_circle,green_rectangle,pink_sphere,yellow_sphere,cyan_sphere"
TEXT_PROMPT = "blue_circle,red_hex,green_circle,green_rectangle,balls"
# TEXT_PROMPT = "objects"


class CentralClientNode(Node):
    def __init__(self) -> None:
        super().__init__("central_client")

        # ---------- Trigger (motion state) clients ----------
        self.left_rest_client = self.create_client(
            Trigger, "/left_rest_server/move_to_state"
        )
        self.left_preaction_client = self.create_client(
            Trigger, "/left_preaction_server/move_to_state"
        )
        self.right_rest_client = self.create_client(
            Trigger, "/right_rest_server/move_to_state"
        )
        self.right_preaction_client = self.create_client(
            Trigger, "/right_preaction_server/move_to_state"
        )

        # ---------- Perception client (RIGHT camera: global registration) ----------
        self.right_perception_client = self.create_client(
            GetObjectLocations, "right_get_object_locations"
        )

        # ---------- Pick clients ----------
        # Left arm: suction pick-and-place server
        self.left_pick_client = self.create_client(
            Pick, "/suction_pick_and_place_server/pick_and_place"
        )
        # Right arm: RWS pick-and-place server
        self.right_pick_client = self.create_client(
            Pick, "/rws_pick_and_place_server/pick_and_place"
        )

        self.bridge = CvBridge()
        self.openai_client = OpenAI()

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

    # ------------------- Perception (right camera) -------------------

    def _make_perception_request(self, prompt_str: str) -> GetObjectLocations.Request:
        req = GetObjectLocations.Request()
        req.prompt = String()
        req.prompt.data = prompt_str
        req.is_local = False
        return req

    def call_right_perception(self):
        service_name = "right_get_object_locations"
        self.get_logger().info(f"Waiting for {service_name}...")
        if not self.right_perception_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(f"{service_name} not available.")
            return None, None

        req = self._make_perception_request(TEXT_PROMPT)
        self.get_logger().info(f"Calling {service_name} with prompt '{TEXT_PROMPT}'")
        future = self.right_perception_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is None:
            self.get_logger().error(f"{service_name} call failed.")
            return None, None

        res = future.result()
        objects = list(res.result.object_position)  # list of ObjectPosition

        self._print_detected_objects(objects)

        # Convert annotated image to OpenCV
        annotated_image_msg = res.result.image
        annotated_image = self.bridge.imgmsg_to_cv2(
            annotated_image_msg, desired_encoding="bgr8"
        )

        return objects, annotated_image

    def _print_detected_objects(self, objects: List[Any]) -> None:
        self.get_logger().info(f"Detected {len(objects)} objects from right camera.")
        for i, obj in enumerate(objects):
            pose: PoseStamped = obj.pose
            p = pose.pose.position
            label = getattr(obj, "label", "")
            self.get_logger().info(
                f"[{i}] id={obj.id}, label='{label}', "
                f"pos=({p.x:.3f}, {p.y:.3f}, {p.z:.3f})"
            )

    # ------------------- LLM call (keeps your prompt logic) -------------------

    @staticmethod
    def _encode_image(image) -> str:
        _, buffer = cv2.imencode(".jpg", image)
        image_base64 = base64.b64encode(buffer).decode("utf-8")
        return image_base64

    def call_llm(
        self, user_prompt: str, objects: List[Any], annotated_image
    ) -> Dict[str, Any]:
        self.get_logger().info("Calling LLM for action planning...")

        base64_annotated_image = self._encode_image(annotated_image)

        dict_obj_list = []
        for obj in objects:
            label = getattr(obj, "label", "")
            dict_obj = {"id": obj.id, "label": label}
            dict_obj_list.append(dict_obj)

        json_detections = json.dumps(dict_obj_list, indent=2)

        # Preamble copied from your ROS1 node (unchanged)
        preamble = (
            'You are a robot controller, you need to write a sequence of actions. '
            'In the image, there are different geometric shapes. You can only execute two types of actions: '
            '"pick_using_left_arm", "pick_using_right_arm", chose the appropriate action for the object '
            'the 3 Dimensional objects are picked with the right arm and the 2 Dimensional objects are picked with the left arm'
            'The only 3 Dimensional objects in the scene are 3 spheres and they look smaller than the 2 Dimensional ones'
            'the pink, yellow and cyan objects are 3d and the red, green and blue are 2d'
            'The labels on the annotated images are not always right, so use your judgement'
            'If there are two objects with very similar locations, it probably means that one of it is a false positive, dont use both the objects in the pick list'
            'depending on the prompt. The output needs to be in the following formats : '
            '{"pick_using_left_arm":[<object_id1>,<object_id2>, ...],'
            '"pick_using_right_arm":[<object_id3>, <object_id4>, ... ]}, this output means that the objects_id '
            '1,2,3,4 .... need to be picked up, object id 1,2 .... need to be picked up using left arm and object '
            'id 3, 4 .... need to be picked up using right arm. Make sure the output format is adhered, '
            'do not include any more description of the reasoning. Refer the image to see which objects are where'
        )

        # GPT-4o multimodal call: text + image
        messages = [
            {
                "role": "system",
                "content": preamble,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"User Prompt: {user_prompt}\n"
                            f"Image Annotations: {json_detections}"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_annotated_image}"
                        },
                    },
                ],
            },
        ]

        completion = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=150,
            temperature=0.0,
        )

        content = completion.choices[0].message.content
        self.get_logger().info(f"Raw LLM output: {content}")

        pick_plan = json.loads(content)

        # Ensure indices are ints
        pick_plan["pick_using_left_arm"] = [
            int(i) for i in pick_plan.get("pick_using_left_arm", [])
        ]
        pick_plan["pick_using_right_arm"] = [
            int(i) for i in pick_plan.get("pick_using_right_arm", [])
        ]

        self.get_logger().info(f"LLM planned objects: {pick_plan}")
        return pick_plan

    # ------------------- Pick calls -------------------

    def _call_pick(self, which: str, obj: Any, idx: int) -> None:
        if which == "left":
            client = self.left_pick_client
            service_name = "/suction_pick_and_place_server/pick_and_place"
        else:
            client = self.right_pick_client
            service_name = "/rws_pick_and_place_server/pick_and_place"

        self.get_logger().info(f"Waiting for {service_name}...")
        if not client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(f"{service_name} not available.")
            return

        req = Pick.Request()

        pose: PoseStamped = obj.pose
        position = pose.pose.position
        req.object_position.x = position.x
        req.object_position.y = position.y
        req.object_position.z = position.z

        # Use label as Pick.srv prompt
        label = getattr(obj, "label", "")
        req.prompt = label if label else "picked_object"
        req.index = idx

        self.get_logger().info(
            f"[{which}] Sending Pick request for object {idx}: "
            f"label='{label}', pos=({position.x:.3f}, {position.y:.3f}, {position.z:.3f})"
        )

        future = client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is not None:
            self.get_logger().info(
                f"[{which}] Pick response (idx={idx}): {future.result()}"
            )
        else:
            self.get_logger().error(
                f"[{which}] Pick service failed for object {idx}: {future.exception()}"
            )

    def _execute_pick_sequence(
        self, which: str, objects: List[Any], indices: List[int]
    ) -> None:
        if not indices:
            self.get_logger().info(f"No objects assigned to {which} arm.")
            return

        self.get_logger().info(
            f"Executing pick sequence on {which} arm for indices: {indices}"
        )
        for idx in indices:
            if idx < 0 or idx >= len(objects):
                self.get_logger().warn(
                    f"Index {idx} out of range [0, {len(objects) - 1}]. Skipping."
                )
                continue
            obj = objects[idx]
            self._call_pick(which, obj, idx)

    # ------------------- Full workflow -------------------

    def run_workflow(self) -> None:
        # left_arm -> rest
        self.get_logger().info("=== Step 1: left arm -> rest ===")
        if not self._call_trigger(
            self.left_rest_client, "left_rest_server/move_to_state"
        ):
            self.get_logger().error("Left rest failed. Aborting workflow.")
            return

        # right arm -> preaction
        self.get_logger().info("=== Step 2: right arm -> preaction ===")
        if not self._call_trigger(
            self.right_preaction_client, "right_preaction_server/move_to_state"
        ):
            self.get_logger().error("Right preaction failed. Aborting workflow.")
            return

        # call right perception (global registration)
        self.get_logger().info("=== Step 3: right perception (global) ===")
        objects, annotated_image = self.call_right_perception()
        if objects is None or annotated_image is None or len(objects) == 0:
            self.get_logger().warn("No objects detected. Aborting workflow.")
            return

        # get prompt (user)
        self.get_logger().info("=== Step 4: get user prompt ===")
        user_prompt = input("Enter the prompt for the task: ").strip()
        if not user_prompt:
            self.get_logger().info("Empty prompt given. Aborting workflow.")
            return

        # plan actions with LLM
        self.get_logger().info("=== Step 5: LLM planning ===")
        pick_plan = self.call_llm(user_prompt, objects, annotated_image)
        left_indices = pick_plan.get("pick_using_left_arm", [])
        right_indices = pick_plan.get("pick_using_right_arm", [])

        # right arm rest
        self.get_logger().info("=== Step 6: right arm -> rest ===")
        if not self._call_trigger(
            self.right_rest_client, "right_rest_server/move_to_state"
        ):
            self.get_logger().error(
                "Right rest failed (post-perception). Continuing anyway."
            )

        # left arm pick and place all its objects
        self.get_logger().info("=== Step 7: left arm pick & place ===")
        self._execute_pick_sequence("left", objects, left_indices)

        # left arm rest
        self.get_logger().info("=== Step 8: left arm -> rest ===")
        if not self._call_trigger(
            self.left_rest_client, "left_rest_server/move_to_state"
        ):
            self.get_logger().error("Left rest failed after picking.")

        # right arm pick and place all its objects
        self.get_logger().info("=== Step 9: right arm pick & place ===")
        self._execute_pick_sequence("right", objects, right_indices)

        # right arm rest
        self.get_logger().info("=== Step 10: right arm -> rest ===")
        if not self._call_trigger(
            self.right_rest_client, "right_rest_server/move_to_state"
        ):
            self.get_logger().error("Right rest failed at end of workflow.")

        self.get_logger().info("=== Workflow finished. ===")


def main(args=None):
    rclpy.init(args=args)
    node = CentralClientNode()

    try:
        node.run_workflow()
    except KeyboardInterrupt:
        node.get_logger().info("Interrupted by user.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
