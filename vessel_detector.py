import cv2
import numpy as np
from vendor.nanodet_upstream import NanoDet
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


