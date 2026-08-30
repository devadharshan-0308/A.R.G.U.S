import cv2
import os
import logging

logger = logging.getLogger(__name__)

def video_frame_generator(video_path, frame_skip=3):
    """
    Ingestion Layer Generator:
    - Reads the video file sequentially.
    - Slices frames based on frame_skip rate (e.g. 3 = every 3rd frame).
    - Yields a structured packet for each processed frame.
    - YOLO handles its own 640x640 letterboxing internally, so raw frames are passed as-is.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"[ERROR] Video file not found at: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"[ERROR] OpenCV could not open video: {video_path}")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_sec = total_frames / fps if fps > 0 else 0

        logger.info("")
        logger.info("=" * 50)
        logger.info("      INGESTION LAYER INITIALIZED")
        logger.info("=" * 50)
        logger.info(f"Video Path       : {video_path}")
        logger.info(f"Original Size    : {orig_w} x {orig_h}")
        logger.info(f"Native FPS       : {fps:.2f}")
        logger.info(f"Total Frames     : {total_frames}")
        logger.info(f"Duration         : {duration_sec:.2f} seconds")
        logger.info(f"Frame Slicing    : Process 1 every {frame_skip} frame(s)")
        logger.info("=" * 50)

        raw_frame_id = 0
        processed_frame_id = 0

        while cap.isOpened():
            ret, raw_frame = cap.read()
            if not ret:
                break

            raw_frame_id += 1

            # Frame Slicing (skip frames)
            if raw_frame_id % frame_skip != 0:
                continue

            processed_frame_id += 1

            # Calculate exact timestamp in seconds
            timestamp_sec = round(raw_frame_id / fps, 2)

            # Standardized Frame Packet
            # Raw frame passed directly — YOLO handles 640x640 letterboxing internally
            packet = {
                "frame_id": processed_frame_id,
                "raw_frame_id": raw_frame_id,
                "timestamp_sec": timestamp_sec,
                "original_shape": (orig_h, orig_w),
                "image": raw_frame,
                "raw_image": raw_frame
            }

            yield packet

    finally:
        cap.release()
        logger.info("[Ingestion Layer] Finished reading all video frames.")