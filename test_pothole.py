from inference_sdk import InferenceHTTPClient, InferenceConfiguration
import base64

# Connect to Roboflow
client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key="qu3R6TKVBUHZyTmQjFz1"
).configure(
    InferenceConfiguration(
        api_key_transport="header"
    )
)

# Read image
with open("C:\SIH\Pothole_Project\pothole2.jpg", "rb") as image_file:
    image_data = base64.b64encode(image_file.read()).decode("utf-8")

print("Image loaded successfully")
print("Sending image to Roboflow...")

# Run workflow
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

print("Roboflow response received successfully!")

print("Number of results:", len(result))

predictions = result[0]["predictions"]

print("Predictions:")

for prediction in predictions["predictions"]:
    pothole_class = prediction["class"].strip()
    confidence = prediction["confidence"] * 100

    x = prediction["x"]
    y = prediction["y"]
    width = prediction["width"]
    height = prediction["height"]

    print("----------------------------")
    print("Pothole:", pothole_class)
    print("Confidence:", round(confidence, 2), "%")
    print("Center X:", x)
    print("Center Y:", y)
    print("Width:", width)
    print("Height:", height)

    # Get annotated image
annotated_image = result[0]["annotated_image"]

# Decode Base64
image_bytes = base64.b64decode(annotated_image)

# Save image
with open("annotated_pothole.jpg", "wb") as f:
    f.write(image_bytes)

print("Annotated image saved successfully!")
print("File: annotated_pothole.jpg")