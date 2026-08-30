from inference_sdk import InferenceHTTPClient, InferenceConfiguration
import base64
import os
import cv2

# --------------------------------
# ROBoflow CONNECTION
# --------------------------------

client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key="qu3R6TKVBUHZyTmQjFz1"
).configure(
    InferenceConfiguration(
        api_key_transport="header"
    )
)

# --------------------------------
# SETTINGS
# --------------------------------

INPUT_FOLDER = "filtered_frames"
OUTPUT_FOLDER = "detected_frames"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --------------------------------
# GET IMAGES IN CORRECT ORDER
# --------------------------------

images = sorted(
    [
        f for f in os.listdir(INPUT_FOLDER)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ],
    key=lambda x: int(
        os.path.splitext(x)[0].split("_")[-1]
    )
)

print("Total frames:", len(images))
print("-----------------------------")

# --------------------------------
# PROCESS EACH IMAGE
# --------------------------------

for filename in images:

    image_path = os.path.join(INPUT_FOLDER, filename)

    print("\nProcessing:", filename)

    # Read image
    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(
            image_file.read()
        ).decode("utf-8")

    print("Image loaded successfully")

    # --------------------------------
    # SEND TO ROBoflow
    # --------------------------------

    result = client.run_workflow(
        workspace_name="vettriesvar-k",
        workflow_id="general-segmentation-api-2",
        images={
            "image": image_data
        },
        parameters={
            "classes": "mild pothole, severe pothole, shallow pothole"
        },
        use_cache=True
    )

    print("Roboflow response received")

    # --------------------------------
    # GET PREDICTIONS
    # --------------------------------

    predictions_data = result[0]["predictions"]

    predictions = predictions_data["predictions"]

    pothole_count = 0

    for prediction in predictions:

        pothole_class = prediction["class"].strip()

        confidence = prediction["confidence"] * 100

        x = prediction["x"]
        y = prediction["y"]
        width = prediction["width"]
        height = prediction["height"]

        pothole_count += 1

        print("----------------------------")
        print("Pothole:", pothole_class)
        print("Confidence:", round(confidence, 2), "%")
        print("Center X:", x)
        print("Center Y:", y)
        print("Width:", width)
        print("Height:", height)

    print(
        f"{filename} -> "
        f"{pothole_count} pothole(s) detected"
    )

    # --------------------------------
    # SAVE ANNOTATED IMAGE
    # --------------------------------

    annotated_image = result[0]["annotated_image"]

    image_bytes = base64.b64decode(
        annotated_image
    )

    output_path = os.path.join(
        OUTPUT_FOLDER,
        filename
    )

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    print("Saved:", output_path)


print("\n-----------------------------")
print("Detection completed!")
print("Results saved in:", OUTPUT_FOLDER)
print("-----------------------------")