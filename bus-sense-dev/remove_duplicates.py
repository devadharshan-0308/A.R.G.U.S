import os
import cv2
from skimage.metrics import structural_similarity as ssim

# Input and output folders
input_folder = "filtered_frames"
output_folder = "unique_frames"

# Create output folder
os.makedirs(output_folder, exist_ok=True)

# Get all image files
images = sorted(
    [
        f for f in os.listdir(input_folder)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ],
    key=lambda x: int(os.path.splitext(x)[0].split("_")[-1])
)

# Similarity threshold
# Higher = more images considered duplicates
SIMILARITY_THRESHOLD = 0.90

previous_image = None
kept_count = 0

for filename in images:

    image_path = os.path.join(input_folder, filename)

    # Read image
    image = cv2.imread(image_path)

    if image is None:
        continue

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # First image is always kept
    if previous_image is None:
        cv2.imwrite(
            os.path.join(output_folder, filename),
            image
        )

        previous_image = gray
        kept_count += 1

        print("Kept:", filename)
        continue

    # Resize current image to previous image size
    gray = cv2.resize(
        gray,
        (previous_image.shape[1], previous_image.shape[0])
    )

    # Calculate similarity
    similarity = ssim(previous_image, gray)

    print(filename, "Similarity:", round(similarity, 3))

    # Keep image if it is sufficiently different
    if similarity < SIMILARITY_THRESHOLD:

        cv2.imwrite(
            os.path.join(output_folder, filename),
            image
        )

        previous_image = gray
        kept_count += 1

        print("  -> Kept")

    else:
        print("  -> Duplicate")


print("\n-----------------------------")
print("Total frames:", len(images))
print("Unique frames:", kept_count)
print("Duplicates removed:", len(images) - kept_count)
print("-----------------------------")