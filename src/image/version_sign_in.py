"""Visual recognition for the recurring seven-day version sign-in page."""
from functools import lru_cache
from pathlib import Path
import re

import cv2
import numpy as np


@lru_cache(maxsize=1)
def _icon():
    path = Path(__file__).resolve().parents[2] / 'assets/images/version_sign_in.png'
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def find_sign_in_icon(frame):
    """Match both light-on-dark and dark-on-light menu icons at screen scale."""
    height, width = frame.shape[:2]
    x0, y0 = int(width * .035), int(height * .24)
    gray = cv2.cvtColor(frame[y0:int(height * .83), x0:int(width * .09)], cv2.COLOR_BGR2GRAY)
    template = _icon()
    best = (0., None)
    for size in range(max(16, int(width * .014)), int(width * .024) + 1):
        scaled = cv2.resize(template, (size, round(size * template.shape[0] / template.shape[1])))
        if scaled.shape[0] > gray.shape[0] or size > gray.shape[1]:
            continue
        result = np.abs(cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED))
        _, score, _, point = cv2.minMaxLoc(result)
        if score > best[0]:
            best = score, (x0 + point[0] + size // 2, y0 + point[1] + scaled.shape[0] // 2)
    return best[1] if best[0] >= .86 else None


def sign_in_layout(boxes):
    """Infer card pitch from OCR day headers, allowing dim claimed days to be missed."""
    days = {}
    for box in boxes:
        text = str(box.name).strip()
        if re.fullmatch(r'0[1-7]', text):
            day = int(text)
            if day in days:
                return None
            days[day] = (box.x + box.width / 2, box.y + box.height / 2)
    if len(days) < 3:
        return None
    ordered = sorted(days.items())
    pitches = [(b[1][0] - a[1][0]) / (b[0] - a[0]) for a, b in zip(ordered, ordered[1:])]
    pitch = float(np.median(pitches))
    if pitch <= 0 or any(abs(p - pitch) > pitch * .12 for p in pitches):
        return None
    y = float(np.median([p[1] for p in days.values()]))
    if any(abs(p[1] - y) > pitch * .12 for p in days.values()):
        return None
    x = float(np.median([p[0] - (day - 1) * pitch for day, p in days.items()]))
    return x, y, pitch


def claimable_days(frame, layout):
    """Require wide gold illumination at BOTH ends, excluding orange ticket art."""
    x, y, pitch = layout
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    found = []
    for day in range(7):
        cx = x + day * pitch
        bands = []
        for top, bottom in ((-.27, -.13), (1.98, 2.15)):
            left, right = round(cx - pitch * .39), round(cx + pitch * .39)
            y0, y1 = round(y + pitch * top), round(y + pitch * bottom)
            if left < 0 or right > width or y0 < 0 or y1 > height:
                return None
            band = hsv[y0:y1, left:right]
            mask = cv2.inRange(band, (10, 45, 190), (40, 255, 255))
            bands.append(float(np.mean(np.any(mask > 0, axis=0))))
        if min(bands) > .65:
            found.append((day + 1, round(cx), round(y + pitch * .85)))
    return found
