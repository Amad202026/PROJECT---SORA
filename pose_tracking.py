"""Retry a failed pose on a mirrored live frame, then restore pixel coordinates."""
import cv2
from pose_quality import pose_is_plausible


def infer_landmarks(frame, people, detector, estimator):
    if len(people) != 1:
        return None, 'unavailable'
    pose = estimator.infer(frame, people[0].copy())
    if pose is not None:
        valid, reason = pose_is_plausible(pose[1], frame.shape[1], frame.shape[0])
        if valid:
            return pose[1], 'original frame'
    mirrored = cv2.flip(frame, 1)
    candidates = detector.infer(mirrored)
    if len(candidates) != 1:
        return None, 'unavailable'
    pose = estimator.infer(mirrored, candidates[0].copy())
    if pose is None:
        return None, 'unavailable'
    landmarks = pose[1].copy()
    landmarks[:, 0] = frame.shape[1] - 1 - landmarks[:, 0]
    # Restore anatomical left/right pairs after reflecting the image.
    for left, right in [(1,4), (2,5), (3,6), (7,8), (9,10), (11,12),
                        (13,14), (15,16), (17,18), (19,20), (21,22),
                        (23,24), (25,26), (27,28), (29,30), (31,32)]:
        landmarks[[left, right]] = landmarks[[right, left]]
    valid, reason = pose_is_plausible(landmarks, frame.shape[1], frame.shape[0])
    return (landmarks, 'mirrored recovery') if valid else (None, reason)
