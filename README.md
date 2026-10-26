# Sora 1.7 - Outcome-aware work companion

Start with START_HERE.md. Extract into a new directory; do not merge old versions.
The Figma design and six team GIF assets are preserved. Notifications are English.

## Changes since 1.6
- Goal controller: observation -> bounded intervention -> observed outcome ->
  one alternative break offer, with pause/dismiss/snooze and trace history.
- Optional IAM-only AWS policy execution, non-blocking fallback, deployment and
  cleanup scripts. Prepared locally, **not yet deployed**.
- Opt-in Windows possible-meeting suppression from active microphone-use
  metadata and running app names; debounced and manually overridable. No audio.
- Repeated sustained mouth-opening cues complement eye closure after warm-up.
  These are possible yawns, not a reliable fatigue diagnosis.
- Camera-facing orientation and observed away intervals are recorded without
  claiming eye gaze, stretching, or sleep verification.
- Experimental straight-straw geometry may supplement vessel proximity. It is
  disabled by default and needs real-video evaluation.
- Video evaluator, synthetic agent replay, submission report/diagram/story/script.

Core modules: sora_ui.py, session_controller.py, companion_agent.py,
agent_policy.py, cloud_policy.py, meeting_detector.py, observation_extras.py,
face_vision.py, visual_signals.py, drinking_auto.py, straw_assist.py.

## Privacy and behavior
Camera frames remain on-device and are not saved by the app. Pause/End/Quit
release the camera. Start-with-Windows is opt-in and opens with the camera off.
Local summaries and agent traces are stored under sessions/. Delete those files
with Sora stopped to clear local history. Evaluation processes only a video path
the user supplies; it does not open a webcam or transmit frames.

AWS is off unless cloud_config.json enables it after user deployment. Its
payload is the goal, stage and five boolean decision flags. Lambda logs only
policy actions. No image, face landmark, window text or audio is uploaded.

Meeting detection uses a Windows registry heuristic that can vary by Windows
version, miss packaged applications/muted calls, and mistake non-call microphone
use for meetings. It is off by default. Use Quiet mode or the meeting override.

The agent is an explicit deterministic policy, not an LLM or a clinical system.
Follow-up is limited to one break offer per posture/distance goal generation;
other reminders retain their existing human controls. Raw vision uncertainty
blocks action; only usable observations or explicit user actions resolve goals.

Posture means relative head/shoulder position, not a measured spine angle.
Distance means relative face size, not centimeters. A sip is a visible motion
estimate, not proof of swallowing, volume or hydration. Sleep is a session-limit
reminder, not detection of sleep. Head orientation is not verified screen gaze.

## Validation and delivery
75 automated tests passed; six synthetic policy scenarios passed. Browser UI
checks passed without camera. Refer to VALIDATION.md for scope and limitations.
Real-video accuracy, physical meeting recognition and AWS execution still need
the team's final verification. See submission/FINAL_TEAM_STEPS_ID.md.

The full archive includes models, original GIFs, pinned dependencies, source,
tests and submission preparation. The technical PDF is small enough for the
35 MB file field; distribute the complete app through a judge-accessible archive
or repository link. Model provenance is in MODEL_SOURCES_V16.md.
