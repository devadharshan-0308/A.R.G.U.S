import cv2
import os
import base64
from inference_sdk import InferenceHTTPClient, InferenceConfiguration


# --------------------------------
# 1. Connect to Roboflow
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
# 2. Create output folder
# --------------------------------

output_folder = r"C:\SIH\filtered_frames"
os.makedirs(output_folder, exist_ok=True)


# --------------------------------
# 3. Open video
# --------------------------------

video_path = r"C:\SIH\Pothole_Project\Porthole_ sample.mp4"

video = cv2.VideoCapture(video_path)

if not video.isOpened():
    print("ERROR: Could not open video!")
    exit()

original_fps = video.get(cv2.CAP_PROP_FPS)

print("Original FPS:", original_fps)


# --------------------------------
# 4. Set target FPS
# --------------------------------

target_fps = 10

frame_interval = max(
    1,
    int(original_fps / target_fps)
)

print("Target FPS:", target_fps)
print("Frame interval:", frame_interval)


# --------------------------------
# 5. Variables
# --------------------------------

frame_number = 0
saved_number = 0


# --------------------------------
# 6. Read video frame by frame
# --------------------------------

while True:

    success, frame = video.read()

    if not success:
        break

    # Process frames according to FPS
    if frame_number % frame_interval == 0:

        filename = "temp_frame.jpg"

        cv2.imwrite(filename, frame)

        print()
        print("Checking frame:", frame_number)


        # --------------------------------
        # 7. Convert image to Base64
        # --------------------------------

        with open(filename, "rb") as image_file:

            image_data = base64.b64encode(
                image_file.read()
            ).decode("utf-8")

        print("Sending image to Roboflow...")


        # --------------------------------
        # 8. Send frame to Roboflow
        # --------------------------------

        result = client.run_workflow(

            workspace_name="vettriesvar-k",

            workflow_id="general-segmentation-api-2",

            images={
                "image": image_data
            },

            parameters={
                "classes":
                "mild pothole, severe pothole, shallow pothole"
            },

            use_cache=True
        )


        # --------------------------------
        # 9. Check predictions
        # --------------------------------

        prediction_data = result[0]["predictions"]

        predictions = prediction_data["predictions"]


        if len(predictions) > 0:

            saved_number += 1


            # --------------------------------
            # 10. Get annotated image
            # --------------------------------

            annotated_base64 = result[0]["annotated_image"]

            image_bytes = base64.b64decode(
                annotated_base64
            )


            # --------------------------------
            # 11. Save annotated image
            # --------------------------------

            output_name = (
                f"{output_folder}\\pothole_{saved_number}.jpg"
            )

            with open(
                output_name,
                "wb"
            ) as output_file:

                output_file.write(image_bytes)


            print("POTHOLE FOUND!")

            print("Saved:", output_name)


            # --------------------------------
            # 12. Print prediction information
            # --------------------------------

            for prediction in predictions:

                print(
                    "Class:",
                    prediction["class"]
                )

                print(
                    "Confidence:",
                    prediction["confidence"]
                )

        else:

            print("No pothole")


    # Move to next frame
    frame_number += 1


# --------------------------------
# 13. Close video
# --------------------------------

video.release()


print()
print("================================")
print("Processing completed!")
print("Total frames checked:", frame_number)
print("Pothole frames saved:", saved_number)
print("================================")