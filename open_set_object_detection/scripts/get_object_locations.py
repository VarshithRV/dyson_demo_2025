#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import CameraInfo, Image
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Float32MultiArray
from typing import List

import cv_bridge
import cv2
import image_geometry
import numpy as np
from groundingdino.util.inference import load_model, load_image, predict
from open_set_object_detection_msgs.msg import ObjectPosition, ObjectPositions
from open_set_object_detection_msgs.srv import GetObjectLocations
import supervision as sv
import torch
from torchvision.ops import box_convert
import tf2_ros
import tf2_geometry_msgs

from rclpy.time import Time
from rclpy.duration import Duration


# Model parameters
BOX_THRESHOLD = 0.35
TEXT_THRESHOLD = 0.25
TEXT_PROMPT = "blue_circle.red_triangle.green_square"

# Camera topic base namespaces (ROS 2)
LEFT_CAMERA_NS = "/camera/left_camera"
RIGHT_CAMERA_NS = "/camera/right_camera"


class Deprojection(Node):
    def __init__(self) -> None:
        super().__init__("deprojection_node")

        # Initialize camera-related variables
        self.left_depth_image = None
        self.left_camera_info = None
        self.left_color_image = None
        self.right_depth_image = None
        self.right_camera_info = None
        self.right_color_image = None

        self.left_bbox = [0.0, 0.0, 0.0, 0.0]
        self.right_bbox = [0.0, 0.0, 0.0, 0.0]

        self.left_camera_model = image_geometry.PinholeCameraModel()
        self.right_camera_model = image_geometry.PinholeCameraModel()

        self.cv_bridge = cv_bridge.CvBridge()
        self.latest_result = None
        self.recursion = 0
        self.source_image_path = "assets/generated_image.jpeg"

        # TF2 buffer and listener
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # Declare parameters (can be overridden via YAML / CLI)
        self.declare_parameter("left_depth_ws_threshold", 1000)
        self.declare_parameter("right_depth_ws_threshold", 1000)

        self.left_depth_threshold = (
            self.get_parameter("left_depth_ws_threshold").value
        )
        self.right_depth_threshold = (
            self.get_parameter("right_depth_ws_threshold").value
        )

        # Load the GroundingDINO model
        self.model = load_model(
            "groundingdino/config/GroundingDINO_SwinT_OGC.py",
            "weights/groundingdino_swint_ogc.pth",
        )
        self.get_logger().info("Loaded the Grounding Dino model")

        # Camera topics (ROS 2, updated names)
        left_camera_color_topic = f"{LEFT_CAMERA_NS}/color/image_raw"
        left_camera_info_topic = f"{LEFT_CAMERA_NS}/aligned_depth_to_color/camera_info"
        left_camera_depth_topic = f"{LEFT_CAMERA_NS}/aligned_depth_to_color/image_raw"

        right_camera_color_topic = f"{RIGHT_CAMERA_NS}/color/image_raw"
        right_camera_info_topic = f"{RIGHT_CAMERA_NS}/aligned_depth_to_color/camera_info"
        right_camera_depth_topic = f"{RIGHT_CAMERA_NS}/aligned_depth_to_color/image_raw"

        # Workspace bounding box topics (assumed new namespaces)
        left_bbox_topic = f"{LEFT_CAMERA_NS}/workspace"
        right_bbox_topic = f"{RIGHT_CAMERA_NS}/workspace"

        # Subscribers
        self.left_depth_image_sub = self.create_subscription(
            Image,
            left_camera_depth_topic,
            self.left_depth_image_callback,
            10,
        )
        self.left_camera_info_sub = self.create_subscription(
            CameraInfo,
            left_camera_info_topic,
            self.left_camera_info_callback,
            10,
        )
        self.left_color_image_sub = self.create_subscription(
            Image,
            left_camera_color_topic,
            self.left_color_image_callback,
            10,
        )
        self.right_depth_image_sub = self.create_subscription(
            Image,
            right_camera_depth_topic,
            self.right_depth_image_callback,
            10,
        )
        self.right_camera_info_sub = self.create_subscription(
            CameraInfo,
            right_camera_info_topic,
            self.right_camera_info_callback,
            10,
        )
        self.right_color_image_sub = self.create_subscription(
            Image,
            right_camera_color_topic,
            self.right_color_image_callback,
            10,
        )

        # Subscribers for workspace bounding boxes
        self.left_bbox_sub = self.create_subscription(
            Float32MultiArray,
            left_bbox_topic,
            self.left_workspace_callback,
            10,
        )
        self.right_bbox_sub = self.create_subscription(
            Float32MultiArray,
            right_bbox_topic,
            self.right_workspace_callback,
            10,
        )

        # Services
        self.left_service = self.create_service(
            GetObjectLocations,
            "left_get_object_locations",
            self.left_get_object_locations,
        )
        self.right_service = self.create_service(
            GetObjectLocations,
            "right_get_object_locations",
            self.right_get_object_locations,
        )

        # Publisher for streamed position
        self.stream_pub = self.create_publisher(
            PoseStamped, "/orange_position", 10
        )

        # Timer for streaming
        self.timer = self.create_timer(0.5, self.publish_stream)

    def __del__(self):
        # This is largely unnecessary in ROS 2 Python but kept for parity
        if hasattr(self, "model"):
            del self.model

    # === Callbacks for workspace bounding boxes ===

    def left_workspace_callback(self, msg: Float32MultiArray):
        self.left_bbox = list(msg.data)

    def right_workspace_callback(self, msg: Float32MultiArray):
        self.right_bbox = list(msg.data)

    # === Annotation and TF utilities ===

    def annotate(
        self,
        image_source: np.ndarray,
        boxes: torch.Tensor,
        logits: torch.Tensor,
        phrases: List[str],
    ) -> np.ndarray:
        h, w, _ = image_source.shape
        boxes = boxes * torch.Tensor([w, h, w, h])
        xyxy = box_convert(
            boxes=boxes, in_fmt="cxcywh", out_fmt="xyxy"
        ).numpy()
        detections = sv.Detections(xyxy=xyxy)
        labels = [
            f"{i}: {phrase} {logit:.2f}"
            for i, (phrase, logit) in enumerate(zip(phrases, logits))
        ]
        bbox_annotator = sv.BoxAnnotator(color_lookup=sv.ColorLookup.INDEX)
        label_annotator = sv.LabelAnnotator(color_lookup=sv.ColorLookup.INDEX)
        annotated_frame = cv2.cvtColor(image_source, cv2.COLOR_RGB2BGR)
        annotated_frame = bbox_annotator.annotate(
            scene=annotated_frame, detections=detections
        )
        annotated_frame = label_annotator.annotate(
            scene=annotated_frame, detections=detections, labels=labels
        )
        return annotated_frame

    def transform_pose(self, pose: PoseStamped, target_frame: str):
        try:
            transform = self.tf_buffer.lookup_transform(
                target_frame,
                pose.header.frame_id,
                Time(),
                timeout=Duration(seconds=3.0),
            )
            transformed_pose = tf2_geometry_msgs.do_transform_pose(
                pose, transform
            )
            return transformed_pose
        except Exception as e:
            self.get_logger().error(f"Transform error: {e}")
            return None

    # === Timer callback ===

    def publish_stream(self):
        if self.latest_result is None:
            return

        if not self.latest_result.object_position:
            return

        position = PoseStamped()
        position.header.frame_id = "world"
        position.header.stamp = self.get_clock().now().to_msg()
        position.pose = self.latest_result.object_position[0].pose.pose
        self.stream_pub.publish(position)

    # === Core 3D position computation ===

    def get_3d_position(
        self,
        x,
        y,
        depth_image,
        camera_info,
        camera_model,
        depth_threshold,
    ):
        if depth_image is None or camera_info is None:
            return None

        # Safety on indices
        h, w = depth_image.shape[:2]
        if x < 0 or x >= w or y < 0 or y >= h:
            self.get_logger().warn(
                f"Pixel ({x}, {y}) outside depth image bounds."
            )
            return None

        depth = depth_image[y, x] / 1000.0  # Convert to meters

        if (
            np.isnan(depth)
            or depth == 0
            or depth > depth_threshold / 1000.0
        ):
            self.get_logger().warn(
                f"Invalid depth at pixel ({x}, {y}) or above threshold."
            )
            self.recursion += 1
            if self.recursion <= 10:
                return self.get_3d_position(
                    x,
                    y,
                    depth_image=depth_image,
                    camera_info=camera_info,
                    camera_model=camera_model,
                    depth_threshold=depth_threshold,
                )
            else:
                self.recursion = 0
                return None

        point_3d = np.array(
            camera_model.projectPixelTo3dRay((x, y))
        ) * depth

        pose = PoseStamped()
        pose.header.frame_id = camera_model.tf_frame
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = float(point_3d[0])
        pose.pose.position.y = float(point_3d[1])
        pose.pose.position.z = float(point_3d[2])
        pose.pose.orientation.w = 1.0

        return self.transform_pose(pose, "world")

    # === Service callbacks ===

    def left_get_object_locations(self, request, response):
        if self.left_color_image is None or not any(self.left_bbox):
            # Empty response
            return response

        x_min, x_max, y_min, y_max = map(int, self.left_bbox)
        cropped_color_image = self.left_color_image[y_min:y_max, x_min:x_max]

        color_image = cv2.cvtColor(cropped_color_image, cv2.COLOR_BGR2RGB)
        cv2.imwrite(self.source_image_path, color_image)

        image_source, image = load_image(self.source_image_path)
        boxes, logits, phrases = predict(
            model=self.model,
            image=image,
            caption=request.prompt.data,
            box_threshold=BOX_THRESHOLD,
            text_threshold=TEXT_THRESHOLD,
        )

        annotated_frame = self.annotate(
            image_source=image_source,
            boxes=boxes,
            logits=logits,
            phrases=phrases,
        )
        cv2.imwrite(
            "inference_images/annotated_image_left.jpg", annotated_frame
        )

        result = ObjectPositions()
        h, w, _ = image_source.shape
        boxes = boxes * torch.Tensor([w, h, w, h])
        xyxy = (
            box_convert(boxes=boxes, in_fmt="cxcywh", out_fmt="xyxy")
            .numpy()
            .astype(int)
        )

        # Inpaint invalid depth points
        left_depth_image = self.left_depth_image
        if left_depth_image is not None:
            mask = (left_depth_image == 0).astype(np.uint8)
            left_depth_image = cv2.inpaint(
                left_depth_image,
                mask,
                inpaintRadius=3,
                flags=cv2.INPAINT_NS,
            )

        for i in range(len(phrases)):
            object_position = ObjectPosition()
            object_position.id = i
            object_position.Class = phrases[i]

            x_center = int((xyxy[i][0] + xyxy[i][2]) / 2) + x_min
            y_center = int((xyxy[i][1] + xyxy[i][3]) / 2) + y_min

            pose = self.get_3d_position(
                x_center,
                y_center,
                depth_image=left_depth_image,
                camera_info=self.left_camera_info,
                camera_model=self.left_camera_model,
                depth_threshold=self.left_depth_threshold,
            )

            if pose is None:
                # Keep behavior similar to original (still append, but with None)
                object_position.pose = PoseStamped()
            else:
                object_position.pose = pose

            object_position.x_min = xyxy[i][0] + x_min
            object_position.y_min = xyxy[i][1] + y_min
            object_position.x_max = xyxy[i][2] + x_min
            object_position.y_max = xyxy[i][3] + y_min

            object_position.x_min_y_min = self.get_3d_position(
                object_position.x_max,
                object_position.y_min,
                depth_image=left_depth_image,
                camera_info=self.left_camera_info,
                camera_model=self.left_camera_model,
                depth_threshold=self.left_depth_threshold,
            )

            object_position.x_max_y_max = self.get_3d_position(
                object_position.x_min,
                object_position.y_max,
                depth_image=left_depth_image,
                camera_info=self.left_camera_info,
                camera_model=self.left_camera_model,
                depth_threshold=self.left_depth_threshold,
            )

            result.object_position.append(object_position)

        result.image = self.cv_bridge.cv2_to_imgmsg(
            annotated_frame, encoding="bgr8"
        )
        self.latest_result = result
        response.result = result
        return response

    def right_get_object_locations(self, request, response):
        if self.right_color_image is None or not any(self.right_bbox):
            return response

        x_min, x_max, y_min, y_max = map(int, self.right_bbox)
        cropped_color_image = self.right_color_image[y_min:y_max, x_min:x_max]

        color_image = cv2.cvtColor(cropped_color_image, cv2.COLOR_BGR2RGB)
        cv2.imwrite(self.source_image_path, color_image)

        image_source, image = load_image(self.source_image_path)
        boxes, logits, phrases = predict(
            model=self.model,
            image=image,
            caption=request.prompt.data,
            box_threshold=BOX_THRESHOLD,
            text_threshold=TEXT_THRESHOLD,
        )

        annotated_frame = self.annotate(
            image_source=image_source,
            boxes=boxes,
            logits=logits,
            phrases=phrases,
        )
        cv2.imwrite(
            "inference_images/annotated_image_right.jpg", annotated_frame
        )

        result = ObjectPositions()
        h, w, _ = image_source.shape
        boxes = boxes * torch.Tensor([w, h, w, h])
        xyxy = (
            box_convert(boxes=boxes, in_fmt="cxcywh", out_fmt="xyxy")
            .numpy()
            .astype(int)
        )

        right_depth_image = self.right_depth_image
        if right_depth_image is not None:
            mask = (right_depth_image == 0).astype(np.uint8)
            right_depth_image = cv2.inpaint(
                right_depth_image,
                mask,
                inpaintRadius=3,
                flags=cv2.INPAINT_NS,
            )

        for i in range(len(phrases)):
            object_position = ObjectPosition()
            object_position.id = i
            object_position.Class = phrases[i]

            x_center = int((xyxy[i][0] + xyxy[i][2]) / 2) + x_min
            y_center = int((xyxy[i][1] + xyxy[i][3]) / 2) + y_min

            pose = self.get_3d_position(
                x_center,
                y_center,
                depth_image=right_depth_image,
                camera_info=self.right_camera_info,
                camera_model=self.right_camera_model,
                depth_threshold=self.right_depth_threshold,
            )

            if pose is None:
                # Original code used "continue" here
                continue

            object_position.pose = pose
            object_position.x_min = xyxy[i][0] + x_min
            object_position.y_min = xyxy[i][1] + y_min
            object_position.x_max = xyxy[i][2] + x_min
            object_position.y_max = xyxy[i][3] + y_min

            object_position.x_min_y_min = self.get_3d_position(
                object_position.x_max,
                object_position.y_min,
                depth_image=right_depth_image,
                camera_info=self.right_camera_info,
                camera_model=self.right_camera_model,
                depth_threshold=self.right_depth_threshold,
            )

            object_position.x_max_y_max = self.get_3d_position(
                object_position.x_min,
                object_position.y_max,
                depth_image=right_depth_image,
                camera_info=self.right_camera_info,
                camera_model=self.right_camera_model,
                depth_threshold=self.right_depth_threshold,
            )

            result.object_position.append(object_position)

        result.image = self.cv_bridge.cv2_to_imgmsg(
            annotated_frame, encoding="bgr8"
        )
        self.latest_result = result
        response.result = result
        return response

    # === Image and camera info callbacks ===

    def left_color_image_callback(self, msg: Image):
        self.left_color_image = self.cv_bridge.imgmsg_to_cv2(
            msg, desired_encoding="passthrough"
        )

    def left_depth_image_callback(self, msg: Image):
        self.left_depth_image = self.cv_bridge.imgmsg_to_cv2(
            msg, desired_encoding="passthrough"
        )

    def left_camera_info_callback(self, msg: CameraInfo):
        self.left_camera_info = msg
        self.left_camera_model.fromCameraInfo(msg)

    def right_color_image_callback(self, msg: Image):
        self.right_color_image = self.cv_bridge.imgmsg_to_cv2(
            msg, desired_encoding="passthrough"
        )

    def right_depth_image_callback(self, msg: Image):
        self.right_depth_image = self.cv_bridge.imgmsg_to_cv2(
            msg, desired_encoding="passthrough"
        )

    def right_camera_info_callback(self, msg: CameraInfo):
        self.right_camera_info = msg
        self.right_camera_model.fromCameraInfo(msg)


def main(args=None):
    rclpy.init(args=args)
    node = Deprojection()
    node.get_logger().info("Deprojection server ready...")
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
