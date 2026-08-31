import cv2
import os


# --------------------------------
# 1. Folder containing pothole images
# --------------------------------

input_folder = r"C:\SIH\filtered_frames"


# --------------------------------
# 2. Output video
# --------------------------------

output_video = r"C:\SIH\Pothole_Project\filtered_potholes.mp4"


# --------------------------------
# 3. Get all images
# --------------------------------

images = []

for filename in os.listdir(input_folder):

    if filename.endswith(".jpg"):
        images.append(filename)


# Sort images in correct order
images.sort(
    key=lambda x: int(
        x.split("_")[1].split(".")[0]
    )
)


# --------------------------------
# 4. Check images
# --------------------------------

if len(images) == 0:

    print("No pothole images found!")

    exit()


# --------------------------------
# 5. Read first image
# --------------------------------

first_image = cv2.imread(
    os.path.join(input_folder, images[0])
)

height, width = first_image.shape[:2]


# --------------------------------
# 6. Create video writer
# --------------------------------

fps = 10

fourcc = cv2.VideoWriter_fourcc(*"mp4v")

video = cv2.VideoWriter(
    output_video,
    fourcc,
    fps,
    (width, height)
)


# --------------------------------
# 7. Add images to video
# --------------------------------

for filename in images:

    image_path = os.path.join(
        input_folder,
        filename
    )

    frame = cv2.imread(image_path)

    video.write(frame)

    print("Added:", filename)


# --------------------------------
# 8. Close video
# --------------------------------

video.release()


print()
print("================================")
print("Filtered video created!")
print("Output:", output_video)
print("Total pothole frames:", len(images))
print("================================")