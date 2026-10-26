from pathlib import Path
import argparse
import time

import cv2
import numpy as np

from vendor.mp_persondet import MPPersonDet
from vendor.mp_pose import MPPose
from pose_tracking import infer_landmarks

from wellness_timers import WellnessTimers
from timer_settings import load_settings
from timer_ui import ReminderCenter as DesktopReminder
from event_logger import EventLogger
from posture_reminder import PostureReminder
from tracking_quality import TrackingQuality
from posture_state import PostureState
from calibration import PostureCalibration
from display_tools import (
    build_monitor,
    draw_upper_body_box,
)

ROOT = Path(__file__).resolve().parent

CAMERA_INDEX = 0
WINDOW_NAME = "Sora v1.4 - Posture and Timers"

# Short window for development. Set to 1200.0 for a 20-minute window.
OBSERVATION_SECONDS = 1200.0

# Landmark indices used by this model.
KEYPOINTS = {
    0: "Nose",
    11: "Left shoulder",
    12: "Right shoulder",
}

# Initial testing thresholds, not calibrated probabilities of correctness.
MIN_VISIBILITY = 0.6
MIN_PRESENCE = 0.6


def get_visible_points(landmarks, width, height):
    points = {}

    for index in KEYPOINTS:
        x, y, z, visibility, presence = landmarks[index]

        if not np.isfinite([x, y, visibility, presence]).all():
            continue

        if visibility < MIN_VISIBILITY or presence < MIN_PRESENCE:
            continue

        if not (0 <= x < width and 0 <= y < height):
            continue

        points[index] = (int(round(x)), int(round(y)))

    return points


def positive_seconds(value):
    number = float(value)
    if not np.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Seconds must be a finite positive number")
    return number


def main():
    parser = argparse.ArgumentParser(description="Sora posture and configurable session timers")
    parser.add_argument("--demo", action="store_true", help="Use shorter timers for testing")
    parser.add_argument("--water-seconds", type=positive_seconds, default=None)
    parser.add_argument("--posture-seconds", type=positive_seconds, default=None)
    parser.add_argument("--posture-only", action="store_true", help="Disable the four time-based wellness reminders")
    parser.add_argument('--settings', type=Path, default=ROOT / 'settings.json')
    args = parser.parse_args()
    try:
        config = load_settings(args.settings, demo=args.demo)
    except (ValueError, OSError) as exc:
        parser.error(f'Unable to load settings: {exc}')
    if args.water_seconds is not None: config['water']['interval_seconds'] = args.water_seconds
    if args.posture_seconds is not None: config['posture']['window_seconds'] = args.posture_seconds
    if args.posture_only:
        for kind in ('water','movement','eyes','sleep'): config[kind]['enabled'] = False
    if cv2.__version__.split(".")[0] != "5":
        raise RuntimeError("OpenCV 5 is required.")

    person_path = (
        ROOT / "models" / "person_detection_mediapipe_2023mar.onnx"
    )
    pose_path = (
        ROOT / "models" / "pose_estimation_mediapipe_2023mar.onnx"
    )

    for path in (person_path, pose_path):
        if not path.exists() or path.stat().st_size < 1_000_000:
            raise RuntimeError(f"Missing or incomplete model: {path.name}")

    print("Loading models...")

    detector = MPPersonDet(
        modelPath=str(person_path),
        scoreThreshold=0.5,
        nmsThreshold=0.3,
        backendId=cv2.dnn.DNN_BACKEND_OPENCV,
        targetId=cv2.dnn.DNN_TARGET_CPU,
    )

    estimator = MPPose(
        modelPath=str(pose_path),
        confThreshold=0.8,
        backendId=cv2.dnn.DNN_BACKEND_OPENCV,
        targetId=cv2.dnn.DNN_TARGET_CPU,
    )

    calibration = PostureCalibration(ROOT / "posture_reference.json")
    tracking_quality = TrackingQuality(report_seconds=10.0)
    posture_state = PostureState()
    reminder = PostureReminder(window_seconds=config['posture']['window_seconds'])
    logger = EventLogger(ROOT / "logs")
    timers = WellnessTimers(config, logger)
    last_posture_state = None
    reminders_paused = False
    # Try DirectShow instead of the MSMF backend that previously failed.
    camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    popup = None

    try:
        if not camera.isOpened():
            raise RuntimeError("Unable to open the camera.")

        popup = DesktopReminder(timers)

        session_started = time.perf_counter()

        logger.write(
            "session_started",
            opencv_version=cv2.__version__,
            window_seconds=reminder.window_seconds,
            timer_settings=config,
            drinking_detection_enabled=False,
            minimum_coverage=reminder.minimum_coverage,
            minimum_lower_fraction=reminder.minimum_lower_fraction,
            enter_drop=posture_state.enter_drop,
            exit_drop=posture_state.exit_drop,
        )

        print(f"Event log: {logger.path}")

        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 640, 900)

        last_status = None
        fps = 0.0
        frame_count = 0
        started = time.perf_counter()

        print("Tracking started. Press Q in the preview to exit.")

        while True:
            success, frame = camera.read()

            if not success or frame is None:
                popup.hide()
                logger.write("camera_read_failed")
                print("Camera frame unavailable. Close other camera apps and restart Sora.")
                break

            # Inference uses the original, unmirrored image.
            height, width = frame.shape[:2]
            brightness = float(cv2.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))[0])
            view_usable = brightness >= config['dark_camera']['brightness_threshold']
            persons = detector.infer(frame) if view_usable else []

            points = {}
            landmarks = None
            status = "No person detected" if view_usable else "Camera view too dark"

            if len(persons) > 1:
                status = "Multiple people detected - use one person"

            elif len(persons) == 1:
                landmarks, pose_source = infer_landmarks(frame, persons, detector, estimator)

                if landmarks is None:
                    status = "Pose unavailable" if pose_source == 'unavailable' else f"Pose uncertain: {pose_source}"

                else:
                    points = get_visible_points(
                        landmarks, width, height
                    )

                    if len(points) == len(KEYPOINTS):
                        status = "Head and shoulders visible" if pose_source == 'original frame' else "Head and shoulders visible (mirror recovery)"
                    else:
                        status = "Tracking uncertain - show head and shoulders"

            # A person can remain present even when the mouth or pose is obscured.
            present = len(persons) == 1
            timers.update(time.perf_counter(), present, reminders_paused, calibration.active, brightness)
            if timers.posture_reset_requested:
                reminder.reset()
                posture_state.reset()
                timers.posture_reset_requested = False

            features = calibration.update(points, width, height)
            tracking_quality.update(status, features)

            if calibration.active:
                posture_state.reset()
                current_posture_state = "CALIBRATING"

            else:
                current_posture_state = posture_state.update(
                    features,
                    calibration.baseline,
                )

            if current_posture_state != last_posture_state:
                logger.write(
                    "posture_state_changed",
                    previous=last_posture_state,
                    current=current_posture_state,
                )

                print(f"Posture observation: {current_posture_state}")
                last_posture_state = current_posture_state

            if reminders_paused or timers.in_break or not timers.enabled['posture']:
                reminder.reset()

            elif calibration.active or calibration.baseline is None:
                reminder.reset()

            else:
                reminder_event = reminder.update(current_posture_state)

                if reminder_event == "REMIND":

                    logger.write(
                        "reminder_shown",
                        coverage=round(reminder.coverage, 4),
                        lower_fraction=round(reminder.lower_fraction, 4),
                        window_seconds=reminder.window_seconds,
                    )

                    print("REMINDER: Consider adjusting your sitting position.")

                elif reminder_event == "RESOLVED":

                    logger.write("posture_recovered")

                    print(
                        "RESOLVED: Your head position is back near your reference."
                    )

            # Mirror only the preview and its drawing coordinates.
            preview = cv2.flip(frame, 1)
            display_points = {
                index: (width - 1 - x, y)
                for index, (x, y) in points.items()
            }

            for index, point in display_points.items():
                cv2.circle(preview, point, 6, (0, 220, 255), -1)

                label_x = max(5, min(point[0] + 8, width - 160))
                label_y = max(65, point[1] - 10)

                cv2.putText(
                    preview,
                    KEYPOINTS[index],
                    (label_x, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 220, 255),
                    1,
                )

            if len(display_points) == len(KEYPOINTS):
                left = display_points[11]
                right = display_points[12]

                shoulder_center = (
                    (left[0] + right[0]) // 2,
                    (left[1] + right[1]) // 2,
                )

                cv2.line(preview, left, right, (0, 220, 0), 2)
                cv2.line(
                    preview,
                    display_points[0],
                    shoulder_center,
                    (0, 220, 0),
                    2,
                )

            frame_count += 1
            elapsed = time.perf_counter() - started

            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                started = time.perf_counter()

            if (
                features is not None
                and calibration.baseline is not None
                and not calibration.active
            ):
                change = (
                    features["head_height_ratio"]
                    - calibration.baseline["head_height_ratio"]
                )

                cv2.putText(
                    preview,
                    f"Head height change: {change:+.3f}",
                    (10, height - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 220, 255),
                    1,
                )
            

            draw_upper_body_box(
                preview,
                display_points,
                current_posture_state,
            )

            monitor = build_monitor(
                preview=preview,
                state=current_posture_state,
                detection_status=status,
                calibration=calibration,
                reminder=reminder,
                features=features,
                session_started=session_started,
                fps=fps,
                reminders_paused=reminders_paused or timers.in_break,
                posture_enabled=timers.enabled['posture'],
                extra_lines=timers.lines(),
            )

            timers.set_posture(reminder.alert_active)
            popup.pump()
            cv2.imshow(WINDOW_NAME, monitor)

            key = cv2.waitKey(1) & 0xFF
            timers.handle_key(key)
            if timers.request_exit:
                break

            if key in (ord("q"), ord("Q")):
                break

            elif key in (ord("c"), ord("C")):
                logger.write(
                    "calibration_requested",
                    previous_reminder_active=reminder.alert_active,
                )
                posture_state.reset()
                reminder.reset()
                popup.hide()
                calibration.start()

            elif key in (ord("p"), ord("P")):
                was_active = reminder.alert_active
                reminders_paused = not reminders_paused

                popup.hide()
                reminder.reset()
                posture_state.reset()

                if reminders_paused:
                    logger.write(
                        "reminders_paused",
                        reminder_active_before_pause=was_active,
                    )
                    print("Reminders paused. Camera remains active.")

                else:
                    logger.write("reminders_resumed")
                    print(
                        "Reminders resumed. "
                        "A new observation period has started."
                    )

            if cv2.getWindowProperty(
                WINDOW_NAME, cv2.WND_PROP_VISIBLE
            ) < 1:
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()

        if popup is not None:
            popup.close()

        logger.write(
            "session_closed",
            reminder_active_at_close=reminder.alert_active,
            observed_seconds=round(timers.observed,1),
        )
        print("Tracking stopped. Camera released.")


if __name__ == "__main__":
    main()
