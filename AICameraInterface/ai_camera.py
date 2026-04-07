"""
Raspberry Pi AI Camera (IMX500) interface with on-camera person detection.
All inference runs on the camera; the host only receives frames and person boxes.

Requires:
  - Raspberry Pi AI Camera (IMX500) attached
  - sudo apt install -y python3-picamera2 imx500-models
  - Picamera2 build that includes IMX500 device support (picamera2.devices.IMX500)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Generator, List, Tuple

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


@dataclass
class BoundingBox:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)

    @property
    def tl(self) -> Tuple[int, int]:
        return (self.x, self.y)

    @property
    def br(self) -> Tuple[int, int]:
        return (self.x + self.w, self.y + self.h)


def select_tracked_person(
    detections: List[BoundingBox],
    previous_center: Tuple[int, int] | None,
    frame_center: Tuple[int, int],
) -> BoundingBox | None:
    """Pick one person to track: nearest to previous center or frame center."""
    if not detections:
        return None
    target = previous_center if previous_center is not None else frame_center
    tx, ty = target
    return min(detections, key=lambda b: (b.center[0] - tx) ** 2 + (b.center[1] - ty) ** 2)


def draw_detections(frame: np.ndarray, boxes: List[BoundingBox], color: Tuple[int, int, int] = (0, 255, 0), thickness: int = 2) -> None:
    if cv2 is None:
        return
    for b in boxes:
        cv2.rectangle(frame, b.tl, b.br, color, thickness)


def draw_tracked(frame: np.ndarray, box: BoundingBox | None, color: Tuple[int, int, int] = (0, 255, 0), thickness: int = 3) -> None:
    if cv2 is None or box is None:
        return
    cv2.rectangle(frame, box.tl, box.br, color, thickness)
    cx, cy = box.center
    cv2.circle(frame, (cx, cy), 6, color, -1)

# Optional: IMX500 and Picamera2 (AI camera path)
IMX500 = None
Picamera2 = None
postprocess_nanodet_detection = None
scale_boxes = None

try:
    from picamera2 import Picamera2
    from picamera2.devices import IMX500 as _IMX500
    IMX500 = _IMX500
    from picamera2.devices.imx500 import postprocess_nanodet_detection as _pnd
    postprocess_nanodet_detection = _pnd
    from picamera2.devices.imx500.postprocess import scale_boxes as _scale_boxes
    scale_boxes = _scale_boxes
except (ImportError, AttributeError):
    pass


# COCO SSD: index 0 is often background, 1 = person (model-dependent; we filter by label)
PERSON_LABEL = "person"

# Default model (object detection; includes person class)
DEFAULT_MODEL = "/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk"


def _frame_to_bgr(frame: np.ndarray) -> np.ndarray:
    """
    Picamera2 XBGR8888 / XRGB8888 buffers are reshaped to (H, W, 4). The first
    three bytes per pixel are already B, G, R in memory (V4L2 BGR32-style layout
    for XBGR8888). Using [:, :, 1:4] wrongly drops B and uses padding as blue,
    which looks black or very dark in OpenCV.
    """
    if frame.ndim == 3 and frame.shape[2] == 4:
        return frame[:, :, :3].copy()
    if frame.ndim == 3 and frame.shape[2] == 3 and cv2 is not None:
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    return frame


def _parse_person_detections(imx500, picam2, metadata, intrinsics, threshold: float) -> List[Tuple[BoundingBox, float]]:
    """Parse IMX500 metadata into person boxes (BoundingBox, confidence)."""
    np_outputs = imx500.get_outputs(metadata, add_batch=True)
    if np_outputs is None:
        return []
    input_w, input_h = imx500.get_input_size()
    postprocess = getattr(intrinsics, "postprocess", None) or (
        getattr(intrinsics, "cpu", None) and intrinsics.cpu.get("post_processing")
    )
    bbox_normalization = getattr(intrinsics, "bbox_normalization", None) or (
        getattr(intrinsics, "cpu", None) and intrinsics.cpu.get("bbox_normalization")
    )
    bbox_order = getattr(intrinsics, "bbox_order", "yx") or (
        getattr(intrinsics, "cpu", None) and intrinsics.cpu.get("bbox_order", "yx")
    )
    try:
        labels = getattr(intrinsics, "labels", None) or (
            getattr(intrinsics, "classes", None) and intrinsics.classes.get("labels") or []
        )
    except Exception:
        labels = []
    labels = labels or []

    if postprocess == "nanodet" and postprocess_nanodet_detection is not None and scale_boxes is not None:
        out = postprocess_nanodet_detection(
            np_outputs[0], conf=threshold, iou_thres=0.65, max_out_dets=20
        )
        boxes = out[0][0] if out else np.zeros((0, 4))
        scores = out[0][1] if out else np.zeros(0)
        classes = out[0][2] if out else np.zeros(0, dtype=np.int32)
        if len(boxes):
            boxes = scale_boxes(boxes, 1, 1, input_h, input_w, False, False)
    else:
        try:
            boxes = np_outputs[0][0]
            scores = np_outputs[1][0]
            classes = np_outputs[2][0]
        except (IndexError, TypeError):
            return []
        if bbox_normalization:
            boxes = boxes / input_h
        if bbox_order == "xy":
            boxes = boxes[:, [1, 0, 3, 2]]

    person_index = None
    for i, lb in enumerate(labels):
        if lb and lb.strip().lower() == "person":
            person_index = i
            break
    if person_index is None and len(labels) > 1:
        person_index = 1  # COCO: 0=background, 1=person

    result = []
    for box, score, cls in zip(boxes, scores, classes):
        if score < threshold:
            continue
        c = int(cls)
        if person_index is not None and c != person_index:
            continue
        if labels and c < len(labels) and labels[c].strip().lower() != "person":
            continue
        # box: (y0, x0, y1, x1) normalized
        y0, x0, y1, x1 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
        try:
            x, y, w, h = imx500.convert_inference_coords((y0, x0, y1, x1), metadata, picam2, "main")
        except Exception:
            continue
        result.append((BoundingBox(x=int(x), y=int(y), w=int(w), h=int(h)), float(score)))
    return result


def ai_camera_available() -> bool:
    """True if the Raspberry Pi AI Camera (IMX500) driver and model appear available."""
    if IMX500 is None or Picamera2 is None:
        return False
    if not os.path.isfile(DEFAULT_MODEL):
        return False
    try:
        # Only check that we can instantiate (device must be present)
        _ = IMX500(DEFAULT_MODEL)
        return True
    except Exception:
        return False


class AICameraFeed:
    """
    Raspberry Pi AI Camera feed with person detection done on the camera (IMX500).
    Yields (frame_bgr, person_boxes) where person_boxes are from on-camera inference.
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL,
        confidence_threshold: float = 0.5,
        width: int = 640,
        height: int = 480,
    ):
        if IMX500 is None or Picamera2 is None:
            raise RuntimeError(
                "Picamera2 with IMX500 support is required. "
                "Install: sudo apt install -y python3-picamera2 imx500-models"
            )
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        self._model_path = model_path
        self._threshold = confidence_threshold
        self._width = width
        self._height = height
        self._imx500 = None
        self._picam2 = None
        self._intrinsics = None

    def __enter__(self) -> AICameraFeed:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()

    def start(self) -> None:
        self._imx500 = IMX500(self._model_path)
        self._intrinsics = self._imx500.network_intrinsics
        if not self._intrinsics:
            from picamera2.devices.imx500 import NetworkIntrinsics
            self._intrinsics = NetworkIntrinsics()
            self._intrinsics.task = "object detection"
        if self._intrinsics.task != "object detection":
            raise RuntimeError("Model is not an object detection network")
        if self._intrinsics.labels is None:
            self._intrinsics.labels = [
                "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
                "truck", "boat", "traffic light", "fire hydrant", "stop sign", "parking meter",
                "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear",
                "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase",
                "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat",
                "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
                "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
                "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut",
                "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet",
                "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
                "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
                "scissors", "teddy bear", "hair drier", "toothbrush",
            ]
        try:
            self._imx500.show_network_fw_progress_bar()
        except Exception:
            pass
        self._picam2 = Picamera2(self._imx500.camera_num)
        rate = getattr(self._intrinsics, "inference_rate", None) or 15.0
        config = self._picam2.create_preview_configuration(
            main={"size": (self._width, self._height), "format": "XBGR8888"},
            controls={"FrameRate": rate},
            buffer_count=8,
        )
        self._picam2.configure(config)
        self._picam2.start()

    def wait_until_ready(self, timeout: float = 15.0, verbose: bool = True) -> None:
        """Block until the sensor produces non-black frames (IMX500 firmware load)."""
        if self._picam2 is None:
            return
        if verbose:
            print("Waiting for AI camera to warm up...", end="", flush=True)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                frame, _ = self.capture_frame_and_persons()
                if frame.mean() > 1.0:
                    if verbose:
                        print(" ready.")
                    return
            except Exception:
                pass
            time.sleep(0.3)
            if verbose:
                print(".", end="", flush=True)
        if verbose:
            print(" timed out (frames may still be dark).")

    def stop(self) -> None:
        if self._picam2 is not None:
            try:
                self._picam2.stop()
            except Exception:
                pass
            self._picam2 = None
        self._imx500 = None
        self._intrinsics = None

    def capture_frame_and_persons(self) -> Tuple[np.ndarray, List[BoundingBox]]:
        """Capture one frame and return (BGR frame, list of person bounding boxes from camera)."""
        if self._picam2 is None or self._imx500 is None:
            raise RuntimeError("Camera not started")
        request = self._picam2.capture_request()
        try:
            metadata = request.get_metadata()
            raw = request.make_array("main")
            frame_bgr = _frame_to_bgr(raw)
            person_list = _parse_person_detections(
                self._imx500, self._picam2, metadata, self._intrinsics, self._threshold
            )
            boxes = [b for b, _ in person_list]
            return frame_bgr, boxes
        finally:
            request.release()

    def frames(self) -> Generator[Tuple[np.ndarray, List[BoundingBox]], None, None]:
        """Infinite generator of (BGR frame, person boxes from on-camera inference)."""
        while True:
            yield self.capture_frame_and_persons()
