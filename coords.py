import json
import os
from typing import Optional

import cv2
import numpy as np

CALIB_PATH = os.getenv("CALIB_PATH", "calibration.json")

_homography: Optional[np.ndarray] = None
_calib_meta: dict = {"ok": False, "points": []}


def load_calibration(path: str = CALIB_PATH) -> dict:
    global _homography, _calib_meta
    if not os.path.isfile(path):
        _homography = None
        _calib_meta = {"ok": False, "points": [], "path": path}
        return _calib_meta
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set_calibration_points(data.get("points", []), path=path, persist=False)


def set_calibration_points(points: list, path: str = CALIB_PATH, persist: bool = True) -> dict:
    global _homography, _calib_meta
    if len(points) < 4:
        raise ValueError("need at least 4 pixel↔robot_mm point pairs")

    src = np.float32([[p["pixel"]["x"], p["pixel"]["y"]] for p in points])
    dst = np.float32([[p["robot_mm"]["x"], p["robot_mm"]["y"]] for p in points])
    H, mask = cv2.findHomography(src, dst, method=0)
    if H is None:
        raise ValueError("could not compute homography")

    _homography = H
    _calib_meta = {
        "ok": True,
        "points": points,
        "path": path,
        "inliers": int(mask.sum()) if mask is not None else len(points),
    }
    if persist:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"points": points}, f, indent=2)
    return _calib_meta


def clear_calibration(path: str = CALIB_PATH) -> dict:
    global _homography, _calib_meta
    _homography = None
    _calib_meta = {"ok": False, "points": [], "path": path}
    if os.path.isfile(path):
        os.remove(path)
    return _calib_meta


def calibration_status() -> dict:
    return dict(_calib_meta)


def pixel_to_robot_mm(x: float, y: float) -> Optional[dict]:
    if _homography is None:
        return None
    pt = np.array([[[x, y]]], dtype=np.float32)
    out = cv2.perspectiveTransform(pt, _homography)[0, 0]
    return {"x": float(out[0]), "y": float(out[1]), "z": 0.0}


def enrich(info: dict, frame_w: int, frame_h: int) -> dict:
    w = max(frame_w, 1)
    h = max(frame_h, 1)
    cx = info["center"]["x"]
    cy = info["center"]["y"]
    bbox = info["bbox"]

    info["normalized"] = {
        "center": {"x": cx / w, "y": cy / h},
        "bbox": {
            "x": bbox["x"] / w,
            "y": bbox["y"] / h,
            "w": bbox["w"] / w,
            "h": bbox["h"] / h,
        },
    }

    robot = pixel_to_robot_mm(cx, cy)
    info["robot_mm"] = robot
    info["calibration_ok"] = robot is not None
    return info
