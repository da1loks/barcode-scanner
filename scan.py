import sys
import cv2

from camera import barcode_info, decode, draw_barcode, open_camera

cam = int(sys.argv[1]) if len(sys.argv) > 1 else 1
cap = open_camera(cam)

if cap is None:
    print(f"камера {cam} не открылась, попробуй другой номер")
    sys.exit(1)

print(f"камера {cam}")
cv2.namedWindow("scan", cv2.WINDOW_NORMAL)
cv2.resizeWindow("scan", 480, 270)

last = None

while True:
    ok, frame = cap.read()
    if not ok:
        break

    for r in decode(frame):
        if not r.text:
            continue
        info = barcode_info(r)
        draw_barcode(frame, info)
        key = (info["code"], info["center"]["x"], info["center"]["y"])
        if key != last:
            c = info["center"]
            print(f"{info['code']}  x={c['x']} y={c['y']}  bbox={info['bbox']}")
            last = key

    cv2.imshow("scan", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
