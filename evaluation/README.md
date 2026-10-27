# Checking SORA

## Application behavior

Run the unit tests from the project root:

```powershell
.\.venv\Scripts\python.exe -B -m unittest test_ui test_timers test_visual_features test_agent test_delivery -q
```

`replay_agent.py` checks six scenarios using synthetic observations: recovery, a persistent position, tracking loss, meeting suppression, dismissal, and a corrected drinking record. It writes results here. These files are generated locally and excluded from Git.

```powershell
.\.venv\Scripts\python.exe -B replay_agent.py
```

These checks cover program behavior. They do not establish camera accuracy.

## Recorded video

Use a video recorded with the participants' permission. Start with a few seconds in the reference position, with the head and shoulders visible. Include drinking from different containers and actions that should not count as a drink, such as touching the face or holding a bottle nearby. Leave at least ten seconds between drinking cycles.

Review the video and record each visible drinking interval in a CSV file:

```csv
start_seconds,end_seconds
8.1,12.4
27.0,31.8
```

Those rows are examples. Replace them with the times from your own recording.

```powershell
.\.venv\Scripts\python.exe evaluate_video.py C:\clips\test.mp4 --labels C:\clips\labels.csv --out evaluation\video_result.json
```

The evaluator reads the supplied video rather than opening a webcam. Its report includes matched, missed, and extra events, along with tracking coverage and processing rate. Keep the video outside the repository. Use separate recordings for tuning and final evaluation.

## Manual checks

- Calibrate, hold a lower-head position, then return to the reference.
- Check that missing tracking does not count as recovery.
- Check dismiss, snooze, pause, end, and restart.
- Try a bottle and a cup; check that each completed drinking cycle counts only once.
- Hold a container near the face without drinking and check for false records.
- Check manual drink confirmation and undo.
- Preview the six animations and check the caption and controls.
- Verify the normal launcher hides recording controls and the demo launcher shows them.

Record failures as well as successful attempts. Previewing a notification is a UI check, not a detection result.
