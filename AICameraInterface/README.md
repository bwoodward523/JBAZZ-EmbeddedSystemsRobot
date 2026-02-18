# AICameraInterface

Raspberry Pi **AI Camera (IMX500)** interface with **person detection and tracking**. All inference runs **on the camera**; the host only receives video frames and person bounding boxes.

## Requirements

- Raspberry Pi AI Camera (IMX500) attached
- Raspberry Pi OS with Picamera2 and IMX500 support

## Setup

1. **Enable the camera** (if not already):
   ```bash
   sudo raspi-config
   # Interface Options → Camera → Enable
   ```

2. **Install the camera stack and AI models**:
   ```bash
   sudo apt update
   sudo apt install -y python3-picamera2 python3-opencv python3-numpy imx500-models
   ```
   Or use a venv (Picamera2 must still be installed via apt):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Usage

- **Live person tracking (with window)**  
  Press `q` or Escape to quit.
  ```bash
  python3 tracker_app.py
  ```

- **Show all detections**  
  Draw every detected person, not just the one being tracked:
  ```bash
  python3 tracker_app.py --show-all
  ```

- **Headless (no display)**  
  For integrating with other code (e.g. pan/tilt servos):
  ```bash
  python3 tracker_app.py --headless
  ```

- **One-shot test**  
  Capture one frame and save to `/tmp/person_test.jpg`:
  ```bash
  python3 test.py
  ```

## Options

| Option         | Default | Description                    |
|----------------|---------|--------------------------------|
| `--width`      | 640     | Frame width                    |
| `--height`     | 480     | Frame height                   |
| `--show-all`   | false   | Draw all people, not just one  |
| `--headless`   | false   | No GUI                         |
| `--confidence` | 0.5     | Detection confidence (0–1)     |

## Using in your own application

```python
from ai_camera import AICameraFeed, BoundingBox, select_tracked_person

with AICameraFeed(width=640, height=480, confidence_threshold=0.5) as cam:
    for frame, person_boxes in cam.frames():
        # person_boxes from on-camera inference
        tracked = select_tracked_person(person_boxes, previous_center=None, frame_center=(320, 240))
        if tracked:
            cx, cy = tracked.center
            # e.g. drive pan/tilt servos toward (cx, cy)
```

## Notes

- Inference runs on the **Raspberry Pi AI Camera (IMX500)** sensor; the host does not run a detection model.
- Requires `imx500-models` and a Picamera2 build with IMX500 device support (standard on recent Raspberry Pi OS with the AI camera stack).
