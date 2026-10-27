# Model and asset provenance

OpenCV Zoo models and adapters are from https://github.com/opencv/opencv_zoo . The original model and adapter license notices are included in `vendor/`.

- NanoDet: https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_nanodet . Shape-based output ordering adapted for OpenCV 5.
- YOLOX: https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_yolox . Revision `25f423d0e04c31a17254620e58febd7386da523b`, model SHA256 `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`. Upstream adapter modified to pass XYWH boxes to OpenCV NMS; detections remain XYXY. Apache 2.0 notice in `vendor/LICENSE_YOLOX`.
- YuNet: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet . Used only as a fallback mouth anchor, not for eye closure.
- ViT tracker: https://github.com/opencv/opencv_zoo/tree/main/models/object_tracking_vittrack . Tracking scores are not calibrated probabilities.
- MediaPipe Face Landmarker: https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python . Official version-1 model bundle: https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task . Runtime pinned to `mediapipe==0.10.32`. The landmark model is not a fatigue classifier.

The team created the six CAMY animations included in this repository. `assets/animations/manifest.json` records SHA256, frame count, duration and union alpha bounds. The UI rendering scales/crops a transient copy only; originals are preserved. Figma provenance and font licenses remain under `web/`.
