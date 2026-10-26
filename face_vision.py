"""Local face landmarks. These measurements are not a fatigue diagnosis."""
import cv2
import numpy as np


class FaceVision:
    def __init__(self, model):
        import mediapipe as mp
        self.mp = mp
        self.engine = mp.tasks.vision.FaceLandmarker.create_from_options(
            mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=2,
                min_face_detection_confidence=.65, min_face_presence_confidence=.65,
                min_tracking_confidence=.65))
        self.timestamp = -1

    def infer(self, frame, now):
        self.timestamp = max(self.timestamp + 1, int(now * 1000))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.engine.detect_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), self.timestamp)
        if len(result.face_landmarks) != 1:
            return None
        h, w = frame.shape[:2]
        p = np.array([(v.x*w, v.y*h) for v in result.face_landmarks[0]])
        if not np.isfinite(p).all(): return None
        span = np.linalg.norm(p[33]-p[263])
        if span < 25: return None
        # Strong rotation invalidates eye aperture and relative distance estimates.
        eye_mid = (p[33]+p[263])/2
        frontal = abs(p[1,0]-eye_mid[0])/span < .28 and abs(p[33,1]-p[263,1])/span < .25
        def ear(ids):
            a,b,c,d,e,f = p[ids]
            return float((np.linalg.norm(b-f)+np.linalg.norm(c-e))/(2*max(1,np.linalg.norm(a-d))))
        mouth = (p[13]+p[14])/2
        return {'mouth':mouth, 'scale':float(span*2), 'span':float(span),
                'ear':max(ear([33,160,158,133,153,144]), ear([362,385,387,263,373,380])),
                'frontal':bool(frontal), 'points':p,
                'mouth_open_ratio':float(np.linalg.norm(p[13]-p[14])/max(1,np.linalg.norm(p[61]-p[291])))}

    def close(self): self.engine.close()
