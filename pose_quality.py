"""Conservative geometry gates; these do not diagnose posture or health."""
import numpy as np


def pose_is_plausible(landmarks, width, height):
    if landmarks is None or len(landmarks) < 13:
        return False, 'missing body points'
    rows = landmarks[[0, 11, 12]]
    if not np.isfinite(rows).all() or np.min(rows[:, 3:5]) < 0.6:
        return False, 'uncertain head or shoulders'
    if np.any(rows[:, 0] < 0) or np.any(rows[:, 0] >= width) or np.any(rows[:, 1] < 0) or np.any(rows[:, 1] >= height):
        return False, 'body points outside image'
    nose, left, right = rows[:, :2]
    span = np.linalg.norm(left - right)
    if span < max(60, 0.16 * width):
        return False, 'shoulder span too small'
    if abs(left[1] - right[1]) > 0.65 * span:
        return False, 'shoulder geometry uncertain'
    if abs(nose[0] - (left[0] + right[0]) / 2) > 0.75 * span:
        return False, 'head and shoulders misaligned'
    eyes = landmarks[[2, 5]]
    if np.isfinite(eyes).all() and np.min(eyes[:, 3:5]) >= 0.6:
        eye_span = np.linalg.norm(eyes[0, :2] - eyes[1, :2])
        if eye_span > 10 and span < 2 * eye_span:
            return False, 'shoulders too narrow for face'
    return True, 'plausible upper body'
