import platform
import cv2
import numpy as np
import zxingcpp


def open_camera(index=1):
    if platform.system() == "Windows":
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY]
    else:
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY]

    for backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
            return cap
        cap.release()
    return None


def decode(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    imgs = [
        frame,
        gray,
        cv2.createCLAHE(2.0, (8, 8)).apply(gray),
        cv2.resize(gray, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC),
    ]
    for img in imgs:
        found = zxingcpp.read_barcodes(img)
        if found:
            return found
    return []


def barcode_info(result):
    pos = result.position
    pts = [
        [int(pos.top_left.x), int(pos.top_left.y)],
        [int(pos.top_right.x), int(pos.top_right.y)],
        [int(pos.bottom_right.x), int(pos.bottom_right.y)],
        [int(pos.bottom_left.x), int(pos.bottom_left.y)],
    ]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
    return {
        "code": result.text,
        "bbox": {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1},
        "center": {"x": (x1 + x2) // 2, "y": (y1 + y2) // 2},
        "polygon": pts,
    }


def draw_barcode(frame, info):
    pts = np.array(info["polygon"], np.int32)
    cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
    c = info["center"]
    cv2.circle(frame, (c["x"], c["y"]), 4, (0, 255, 0), -1)
    label = f"{info['code']} @ {c['x']},{c['y']}"
    cv2.putText(frame, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
