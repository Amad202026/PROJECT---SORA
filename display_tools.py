import time

import cv2
import numpy as np


STATE_LABELS = {
    "UNKNOWN": "Tracking unavailable / not confirmed",
    "CALIBRATING": "Calibrating",
    "NEAR_REFERENCE": "Near reference",
    "LOWER_HEAD_POSITION": "Lower head position",
}

STATE_COLORS = {
    "UNKNOWN": (170, 170, 170),
    "CALIBRATING": (255, 200, 0),
    "NEAR_REFERENCE": (80, 220, 120),
    "LOWER_HEAD_POSITION": (0, 180, 255),
}


def format_duration(seconds):
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def draw_upper_body_box(preview, display_points, state):
    """Draw a region around the observed nose and shoulders."""
    required = (0, 11, 12)

    if not all(index in display_points for index in required):
        return

    coordinates = np.array(
        [display_points[index] for index in required],
        dtype=np.int32,
    )

    height, width = preview.shape[:2]
    padding = 35

    x1 = max(0, int(coordinates[:, 0].min()) - padding)
    y1 = max(0, int(coordinates[:, 1].min()) - padding)
    x2 = min(width - 1, int(coordinates[:, 0].max()) + padding)
    y2 = min(height - 1, int(coordinates[:, 1].max()) + padding)

    color = STATE_COLORS.get(state, (170, 170, 170))

    cv2.rectangle(preview, (x1, y1), (x2, y2), color, 2)

    cv2.putText(
        preview,
        "Upper-body region",
        (x1 + 5, min(height - 5, y1 + 20)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        1,
    )


def build_monitor(
    preview,
    state,
    detection_status,
    calibration,
    reminder,
    features,
    session_started,
    fps,
    reminders_paused=False,
    extra_lines=None,
    posture_enabled=True,
):
    """Append a status panel below the camera image."""
    now = time.perf_counter()

    period_elapsed = (
        min(now - reminder.started_at, reminder.window_seconds)
        if reminder.started_at is not None
        else 0.0
    )

    known_seconds = reminder.coverage * reminder.window_seconds
    lower_seconds = known_seconds * reminder.lower_fraction

    if not posture_enabled:
        reminder_label = "Posture reminder disabled"
    elif reminders_paused:
        reminder_label = "Paused - camera remains active"
    elif calibration.active:
        reminder_label = "Calibration in progress"
    elif calibration.baseline is None:
        reminder_label = "Calibration required"
    elif reminder.alert_active:
        reminder_label = "Reminder active - waiting for recovery"
    elif period_elapsed < reminder.window_seconds:
        reminder_label = "Collecting observation history"
    elif reminder.coverage < reminder.minimum_coverage:
        reminder_label = "Waiting for more valid observations"
    else:
        reminder_label = "Monitoring"

    if features is not None and calibration.baseline is not None:
        change = (
            features["head_height_ratio"]
            - calibration.baseline["head_height_ratio"]
        )
        change_label = f"{change:+.3f}"
    else:
        change_label = "N/A"

    lines = [
        f"Status: {STATE_LABELS.get(state, state)}",
        f"Detection: {detection_status}",
        (
            f"Session: {format_duration(now - session_started)}"
            f"   FPS: {fps:.1f}"
        ),
        (
            f"Observation window: {period_elapsed:.1f}"
            f" / {reminder.window_seconds:.0f}s"
        ),
        (
            f"Known time: {known_seconds:.1f}s"
            f"   Coverage: {reminder.coverage:.0%}"
        ),
        (
            f"Lower-head time: {lower_seconds:.1f}s"
            f"   Share of known time: {reminder.lower_fraction:.0%}"
        ),
        f"Reminder: {reminder_label}",
        (
            f"Head height change: {change_label}"
            f"   C: calibrate   P: pause/resume   Q: quit"
        ),
        calibration.message,
    ]

    if extra_lines:
        lines.extend(extra_lines)

    panel_height = 20 * len(lines) + 18

    output = cv2.copyMakeBorder(
        preview,
        0,
        panel_height,
        0,
        0,
        cv2.BORDER_CONSTANT,
        value=(25, 25, 25),
    )

    first_y = preview.shape[0] + 22

    for index, line in enumerate(lines):
        color = (
            STATE_COLORS.get(state, (220, 220, 220))
            if index == 0
            else (230, 230, 230)
        )

        cv2.putText(
            output,
            line,
            (10, first_y + index * 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            color,
            1,
            cv2.LINE_AA,
        )

    return output

