"""Local visual evidence, not a measurement of swallowing or hydration."""
from dataclasses import dataclass
import math

import cv2
import numpy as np
from vendor.nanodet_upstream import NanoDet
from registered_vessel import RegisteredVessel
from face_anchor import FaceAnchor
from vessel_views import VesselViews
from vessel_follower import VesselFollower
from pose_quality import pose_is_plausible


VESSELS = {39: 'bottle', 40: 'glass', 41: 'cup'}


class VesselDetector(NanoDet):
    """OpenCV Zoo NanoDet with shape-based output ordering for OpenCV 5."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This pinned ONNX has three output scales; upstream lists a fourth unused scale.
        self.strides = self.strides[:3]
        self.anchors_mlvl = self.anchors_mlvl[:3]

    def post_process(self, outputs):
        ordered = []
        for anchors in self.anchors_mlvl:
            count = len(anchors)
            for channels in (80, 32):
                matches = [a for a in outputs if a.shape == (1, count, channels)
                           or a.shape == (count, channels)]
                if len(matches) != 1:
                    raise RuntimeError(f'Unexpected NanoDet output shapes: {[a.shape for a in outputs]}')
                ordered.append(matches[0])
        return super().post_process(ordered)

    def detect(self, frame):
        height, width = frame.shape[:2]
        scale = min(416 / width, 416 / height)
        new_width, new_height = round(width * scale), round(height * scale)
        left, top = (416 - new_width) // 2, (416 - new_height) // 2
        resized = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), (new_width, new_height))
        canvas = np.zeros((416, 416, 3), np.uint8)
        canvas[top:top + new_height, left:left + new_width] = resized
        detections = []
        for item in self.infer(canvas):
            class_id = int(item[5])
            if class_id not in VESSELS:
                continue
            box = item[:4].astype(float)
            box[[0, 2]] = np.clip((box[[0, 2]] - left) * width / new_width, 0, width - 1)
            box[[1, 3]] = np.clip((box[[1, 3]] - top) * height / new_height, 0, height - 1)
            if min(box[2:] - box[:2]) < 8:
                continue
            detections.append({'box': box, 'label': VESSELS[class_id], 'score': float(item[4])})
        return detections


def point_box_distance(point, box):
    x, y = point
    x1, y1, x2, y2 = box
    return math.hypot(max(x1 - x, 0, x - x2), max(y1 - y, 0, y - y2))


def iou(a, b):
    intersection = np.maximum(0, np.minimum(a[2:], b[2:]) - np.maximum(a[:2], b[:2])).prod()
    union = (a[2:] - a[:2]).prod() + (b[2:] - b[:2]).prod() - intersection
    return float(intersection / union) if union > 0 else 0.0


@dataclass
class DrinkEvidence:
    valid: bool = False
    track_id: int = -1
    kind: str = 'NONE'
    distance: float = 999.0
    label: str = ''
    score: float = 0.0
    hand_near: bool = False
    straw_line: bool = False
    reason: str = 'Show your face and vessel'
    mouth_source: str = 'unavailable'
    vessel_source: str = 'model'


class DrinkVision:
    def __init__(self, model_path):
        self.detector = VesselViews(VesselDetector(str(model_path), prob_threshold=0.35))
        self.follower = VesselFollower()
        self.registration_generation = 0
        self.tracks = {}
        self.next_track = 0
        self.detections = []
        self.mouth = None
        self.line = None
        self.selected = None
        self.registered = RegisteredVessel()
        self.face_anchor = FaceAnchor()
        self.registered_detection = None
        self.registered_at = None
        self.pose_context = None
        self.mouth_source = 'unavailable'

    def register(self, frame, roi, now):
        self.registration_generation += 1
        self.follower.clear()
        return self.registered.register(frame, roi, now)

    def track_registered(self, frame, now):
        self.registered_detection = self.registered.update(frame, now)
        self.registered_at = now
        if self.registered_detection is not None:
            self.registered_detection['identity'] = 2000000 + self.registration_generation
        self.follower.update(frame, now)

    @staticmethod
    def point(landmarks, index, width, height):
        if landmarks is None or len(landmarks) <= index:
            return None
        row = landmarks[index]
        if not np.isfinite(row).all() or min(row[3:5]) < 0.45:
            return None
        if not (0 <= row[0] < width and 0 <= row[1] < height):
            return None
        return np.array(row[:2], dtype=float)

    def update_tracks(self, detections, now):
        self.tracks = {key: value for key, value in self.tracks.items() if now - value['seen'] <= 0.8}
        unused = set(self.tracks)
        for detection in detections:
            box = detection['box']
            candidates = []
            for key in unused:
                if key >= 1000000 and 'identity' not in detection:
                    continue
                previous = self.tracks[key]['box']
                overlap = iou(box, previous)
                center_distance = np.linalg.norm((box[:2] + box[2:] - previous[:2] - previous[2:]) / 2)
                diagonal = max(20, np.linalg.norm(previous[2:] - previous[:2]))
                if overlap >= 0.1 or center_distance < 0.6 * diagonal:
                    candidates.append((overlap - center_distance / diagonal * 0.1, key))
            if 'identity' in detection:
                key = detection['identity']
                unused.discard(key)
            elif candidates:
                key = max(candidates)[1]
                unused.remove(key)
            else:
                self.next_track += 1
                key = self.next_track
            detection['track_id'] = key
            self.tracks[key] = dict(detection, seen=now)

    @staticmethod
    def straw_hint(frame, mouth, box, scale):
        """A line connecting mouth to vessel top is only a weak straw-like cue."""
        x1, y1, x2, y2 = box
        if not (0.06 * scale < y1 - mouth[1] < 0.65 * scale
                and x1 - 0.12 * scale <= mouth[0] <= x2 + 0.12 * scale):
            return None
        height, width = frame.shape[:2]
        left = max(0, int(min(x1, mouth[0]) - 0.12 * scale))
        right = min(width, int(max(x2, mouth[0]) + 0.12 * scale))
        top = max(0, int(mouth[1] - 0.12 * scale))
        bottom = min(height, int(y1 + 0.2 * (y2 - y1)))
        crop = frame[top:bottom, left:right]
        if crop.size == 0:
            return None
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 70, 160)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=12,
            minLineLength=max(12, int(0.08 * scale)), maxLineGap=max(4, int(0.06 * scale)))
        if lines is None:
            return None
        for line in np.asarray(lines).reshape(-1, 4):
            a, b = line.reshape(2, 2).astype(float) + [left, top]
            if np.linalg.norm(b - mouth) < np.linalg.norm(a - mouth):
                a, b = b, a
            top_band = [x1, y1 - 0.1 * scale, x2, y1 + 0.2 * (y2 - y1)]
            if np.linalg.norm(a - mouth) < 0.12 * scale and point_box_distance(b, top_band) < 0.08 * scale:
                return (a, b)
        return None

    def observe(self, frame, landmarks, now, person_present=True):
        self.mouth = self.line = self.selected = None
        self.mouth_source = 'unavailable'
        self.detections = self.detector.detect(frame)
        if self.registered_at != now:
            self.track_registered(frame, now)
        registered = self.registered_detection
        if self.registered.tracker is not None:
            if registered is not None:
                # Preserve the explicit vessel identity, even if the semantic detector flickers.
                matches=[d for d in self.detections if iou(registered['box'],d['box'])>=0.25]
                if matches:
                    registered=dict(registered,box=max(matches,key=lambda d:d['score'])['box'])
                self.detections=[registered]
            else:
                self.detections=[]
        else:
            followed=self.follower.reconcile(self.detections,frame,now,allow_start=person_present)
            if followed is not None:
                self.detections=[followed]
        self.update_tracks(self.detections, now)
        height, width = frame.shape[:2]
        if not pose_is_plausible(landmarks, width, height)[0]:
            landmarks = None
        points = {i: self.point(landmarks, i, width, height) for i in (9, 10, 11, 12, 15, 16, 19, 20)}
        if not person_present:
            self.pose_context = None
            return DrinkEvidence(reason='Containers checked; need exactly one person for sip detection')
        face = self.face_anchor.observe(frame)
        if self.face_anchor.multiple:
            self.pose_context = None
            return DrinkEvidence(reason='Multiple faces visible; sip detection paused')
        # Facial landmarks inferred inside a vessel are unreliable under occlusion.
        if face is not None and any(point_box_distance(face[0],d['box']) == 0 for d in self.detections):
            face = None
        if face is not None:
            mouth, scale = face
            self.pose_context = (now, mouth.copy(), scale)
            self.mouth_source = 'face landmarks'
        elif (all(points[i] is not None for i in (9, 10, 11, 12))
              and not any(point_box_distance((points[9]+points[10])/2,d['box'])==0 for d in self.detections)):
            mouth = (points[9] + points[10]) / 2
            scale = float(np.linalg.norm(points[11] - points[12]))
            self.pose_context = (now, mouth.copy(), scale)
            self.mouth_source = 'pose landmarks'
        elif self.pose_context is not None and now - self.pose_context[0] <= 3.0:
            _, mouth, scale = self.pose_context
            self.mouth_source = 'recent mouth reference'
        else:
            detail = 'Container detected; mouth unavailable - W if you drank' if self.detections else 'No container detected; mouth unavailable'
            return DrinkEvidence(reason=detail)
        self.mouth = mouth
        if not self.detections:
            return DrinkEvidence(valid=True, reason='No container detected - R to register yours', mouth_source=self.mouth_source)
        vessel = min(self.detections, key=lambda item: point_box_distance(mouth, item['box']))
        self.selected = vessel
        box = vessel['box']
        distance = point_box_distance(mouth, box) / scale
        vessel_source = vessel.get('source', 'model')
        if self.mouth_source not in ('face landmarks', 'pose landmarks'):
            kind = 'OCCLUDED' if distance < 0.12 else 'NONE'
            return DrinkEvidence(valid=True, track_id=vessel['track_id'], kind=kind,
                distance=distance, label=vessel['label'], score=vessel['score'],
                reason='Mouth hidden; recent reference only',
                mouth_source=self.mouth_source, vessel_source=vessel_source)
        hands = [points[i] for i in (15, 16, 19, 20) if points[i] is not None]
        hand_near = any(point_box_distance(hand, box) < 0.18 * scale
                        and np.linalg.norm(hand - mouth) < 0.85 * scale for hand in hands)
        # A very large box swallowing the entire face is not a useful contact cue.
        edge_distance = min(abs(mouth[0] - box[0]), abs(mouth[0] - box[2]),
                            abs(mouth[1] - box[1]), abs(mouth[1] - box[3])) / scale
        direct = distance <= 0.09 and edge_distance < 0.22
        self.line = self.straw_hint(frame, mouth, box, scale)
        kind = 'DIRECT' if direct and hand_near else 'UNCERTAIN' if direct else 'STRAW' if self.line is not None else 'NONE'
        if direct and vessel_source == 'registered':
            kind = 'REGISTERED'
        reasons = {'DIRECT': 'Container + mouth + hand aligned',
                   'UNCERTAIN': 'Container near mouth; hand evidence missing',
                   'STRAW': 'Straw-like line only; W if you drank',
                   'REGISTERED': 'Registered vessel near mouth',
                   'NONE': 'Container visible; no drinking contact'}
        return DrinkEvidence(True, vessel['track_id'], kind, distance, vessel['label'],
                             vessel['score'], hand_near, self.line is not None, reasons[kind],
                             self.mouth_source, vessel_source)

    def clear(self):
        self.tracks.clear()
        self.detections = []
        self.mouth = self.line = self.selected = None
        self.mouth_source = 'unavailable'
        self.pose_context = None
        self.registered.clear()
        self.follower.clear()
        self.registered_detection = None
        self.registered_at = None

    def draw(self, preview):
        width = preview.shape[1]
        for vessel in self.detections:
            x1, y1, x2, y2 = map(int, vessel['box'])
            left, right = width - 1 - x2, width - 1 - x1
            cv2.rectangle(preview, (left, y1), (right, y2), (255, 190, 70), 2)
            label = f"{vessel['label']} (tracking)" if vessel.get('source') in ('registered','tracked_model') else f"{vessel['label']} {vessel['score']:.2f}"
            cv2.putText(preview, label, (max(0, left), max(15, y1 - 7)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 190, 70), 1, cv2.LINE_AA)
        if self.mouth is not None:
            p = (width - 1 - int(self.mouth[0]), int(self.mouth[1]))
            thickness = -1 if self.mouth_source in ('face landmarks', 'pose landmarks') else 1
            cv2.circle(preview, p, 4, (255, 120, 255), thickness)
        if self.line is not None:
            a, b = [(width - 1 - int(p[0]), int(p[1])) for p in self.line]
            cv2.line(preview, a, b, (255, 120, 255), 2)
