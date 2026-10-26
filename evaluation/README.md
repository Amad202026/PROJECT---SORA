# Reproducible evaluation

Run all tests:
`python -B -m unittest test_ui test_timers test_visual_features test_agent test_delivery -q`

Run `python replay_agent.py` for six synthetic control-policy scenarios. These
are explicitly marked synthetic; they do not measure camera/model accuracy.
Review `policy_trace.jsonl` for observation -> decision -> tool -> outcome.

## Real video test (requires your participation)

Record a local video with everyone's consent. Do not upload it by default.
Start with 3 seconds in your reference posture, with head/shoulders visible.
Then record cup, bottle and straw sips with at least 10 seconds between sips;
include showing a cup without drinking, touching your face, talking, turning
away, looking down, poor lighting and an empty chair. Repeat with varied
lighting and more than one consenting participant before claiming general accuracy.

Suggested minimum pilot: 10 positive cycles per vessel type plus 30 negative
actions. Do not tune on the same videos used for final reported metrics. Keep
the 1.6 baseline archive for a fair comparison on identical clips/settings.

Watch the video and annotate each actual visible drinking-motion interval
(approach to completed retreat), in seconds. `labels.csv`:

```csv
start_seconds,end_seconds
8.1,12.4
27.0,31.8
```

These rows are an illustration, not fabricated ground truth. Replace them with
reviewed times. A negative-only clip has just the header. Run:

```powershell
.\.venv\Scripts\python.exe evaluate_video.py C:\path\test.mp4 --labels C:\path\labels.csv --out evaluation\cup_result.json
.\.venv\Scripts\python.exe evaluate_video.py C:\path\straw.mp4 --labels C:\path\straw_labels.csv --straw --out evaluation\straw_result.json
```

No webcam is opened by this command. It runs the real OpenCV 5 person/pose and
vessel pipeline plus face landmarks, counts misses and extra/duplicate events,
and reports precision, recall, coverage and offline throughput. One predicted
event may match only one annotated interval, with up to 2 seconds after retreat.
Missing denominator metrics are null, never inflated to 100%. Model load time
is excluded from throughput. Posture labels are observations, not independently
validated posture accuracy. Frames, raw face landmarks and video are not copied
to the report or uploaded. Keep private video files outside the submission zip.

## Human acceptance checks

- Verify all 6 original animations, transparent background, English caption,
  × dismiss, ✓ action and Ⅱ snooze. Test mouse and keyboard.
- Posture: move down briefly, stay lower through the window, then recover.
- Dismiss must stop follow-ups. Unknown tracking must not count as recovery.
- Pause/End must release webcam. Start a new session with timers reset.
- Automatic meeting detection is opt-in; test a real call and a non-call mic
  session. False meeting signals are expected; test manual override.
- Distance is relative; moving the camera requires recalibration.
- Yawns/closed eyes are unvalidated cues; speech, glasses and occlusion are negatives.
- Cloud: verify one AWS-sourced trace and one network-failure local fallback.

The distribution contains no invented real-video accuracy results.
