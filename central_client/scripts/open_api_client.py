import json
import base64
import cv2
import numpy as np
from openai import OpenAI


TEXT_PROMPT = "blue_circle.red_hex.green_rectangle.green_circle.blue_rectangle.light_blue_ball.yellow_ball.pink_ball"


def load_image_as_numpy_and_base64(image_path: str):
    """
    Load an image from disk as a NumPy array and return:
      - the NumPy array (H, W, 3)
      - the base64-encoded JPEG string
    """
    # Read image as BGR NumPy array
    img_np = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img_np is None:
        raise FileNotFoundError(f"Could not read image at path: {image_path}")

    # Encode as JPEG in memory
    success, buffer = cv2.imencode(".jpg", img_np)
    if not success:
        raise RuntimeError("Could not encode image as .jpg")

    img_bytes = buffer.tobytes()
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")

    return img_np, img_base64


def llm(prompt, object_detections, image_path: str = "sample.png"):
    """
    Call OpenAI to decide which arm should pick which objects,
    using both text and an uploaded image (sample.png in same directory).

    Args:
        prompt (str): User's natural language instruction.
        object_detections (list): Iterable of objects with fields/keys:
                                  - id
                                  - Class
        image_path (str): Path to the image (default: 'sample.png').

    Returns:
        dict: {
            "pick_using_left_arm": [obj_id_1, obj_id_2, ...],
            "pick_using_right_arm": [obj_id_3, obj_id_4, ...]
        }
    """

    # ----- 1) Prepare detections as JSON -----
    dict_obj_list = []
    for obj in object_detections:
        # supports both attribute-style and dict-style access
        obj_id = getattr(obj, "id", obj.get("id"))
        obj_label = getattr(obj, "Class", obj.get("Class"))
        dict_obj_list.append({"id": obj_id, "label": obj_label})

    json_detections = json.dumps(dict_obj_list, indent=2)

    # ----- 2) Load image as NumPy and base64 -----
    # img_np is a NumPy array (H, W, 3), kept if you want to further process it
    img_np, img_base64 = load_image_as_numpy_and_base64(image_path)

    # (Optional) just to emphasize it's NumPy:
    assert isinstance(img_np, np.ndarray)

    # ----- 3) Build prompts -----
    preamble = (
        'You are a robot controller: you must output a sequence of actions. '
        'In the scene there are geometric shapes. You can only execute two '
        'types of actions: "pick_using_left_arm" and "pick_using_right_arm". '
        'You must output JSON in the exact format: '
        '{"pick_using_left_arm":[<object_id1>,<object_id2>,...],'
        '"pick_using_right_arm":[<object_id3>,<object_id4>,...]} '
        'Do NOT include any explanations or extra text outside of valid JSON.'
    )
    preamble2 = (
        "The right arm has a fingered gripper and the left arm has a suction gripper."
    )
    preamble3 = (
        "The suction gripper can pick planar and 2D objects (e.g., rectangles, circles, hexagons)."
    )
    preamble4 = (
        "The fingered gripper can pick 3D discrete objects like apples and other fruits."
    )
    preamble5 = "Use this information to decide which arm should pick each object."
    preamble6 = (
        "The labels may be slightly inaccurate; use reasoning to choose the correct objects."
    )

    client = OpenAI()

    # ----- 4) Call OpenAI with text + image -----
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": preamble},
            {"role": "system", "content": preamble2},
            {"role": "system", "content": preamble3},
            {"role": "system", "content": preamble4},
            {"role": "system", "content": preamble5},
            {"role": "system", "content": preamble6},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"User Prompt: {prompt}\n\n"
                            f"Object Detections (JSON):\n{json_detections}"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_base64}"
                        },
                    },
                ],
            },
        ],
        max_tokens=150,
        temperature=0,
    )

    # # ----- 5) Parse JSON response -----
    raw_content = completion.choices[0].message.content
    # pick_list = json.loads(raw_content)

    # # Ensure IDs are ints
    # pick_list["pick_using_left_arm"] = [
    #     int(obj_id) for obj_id in pick_list.get("pick_using_left_arm", [])
    # ]
    # pick_list["pick_using_right_arm"] = [
    #     int(obj_id) for obj_id in pick_list.get("pick_using_right_arm", [])
    # ]
    print(raw_content)
    # return pick_list


if __name__ == "__main__":
    # Minimal demo usage (no ROS)
    example_prompt = "Pick all rectangles with the left arm and balls with the right arm."
    example_detections = [
        {"id": 0, "Class": "green_rectangle"},
        {"id": 1, "Class": "yellow_ball"},
        {"id": 2, "Class": "blue_circle"},
    ]
    llm(example_prompt, example_detections, image_path="sample.png")
