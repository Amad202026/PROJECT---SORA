<p align="center">
  <img src="web/assets/sora-logo.png" alt="SORA" width="110">
</p>

# SORA

SORA is a desktop companion for people who spend a lot of time working or studying at a computer. It uses a webcam to notice changes from a calibrated sitting position and shows reminders through CAMY, our animated character.

The app runs on Windows. Its dashboard opens in your browser, and reminders appear directly on the desktop.

## What it does

- Compares head and shoulder position with your own reference.
- Suggests moving back when your face stays closer to the camera.
- Reminds you to drink, move, rest your eyes, or end a long session.
- Offers a short break when a posture reminder has not led to an observed change.
- Keeps session history and a trace of reminder decisions.
- Lets you dismiss, snooze, pause, and correct drinking records.

Bottle and cup recognition is still experimental. SORA looks for a sequence of movement toward the mouth and back away. It can miss a drink or count one incorrectly, especially when the container hides the face. Manual confirmation and undo are available.

## Run it

You need Windows, a webcam, and Python with Tkinter. Development currently uses Python 3.14. The included dependency lock file records the package versions used by the project.

1. Clone or download this repository and extract it into its own folder.
2. Run **Setup Sora UI.bat** to create the Python environment and install dependencies.
3. Run **Start Sora UI.bat**.
4. Click **Start session**, then calibrate while sitting in your reference position.
5. Use **Open camera** to check the landmarks and detection status.

The models and animations are included. Initial setup needs an internet connection to install Python packages. Keep the launcher running while you use the dashboard.

If you prefer PowerShell, run these commands from the project folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe sora_ui.py
```

## Demo mode

Open **Start Sora UI Demo.bat** for shorter reminder intervals. It also includes **Record notifications**, which lets you preview each animation for a recording. These buttons trigger the notification manually; they do not test the detector.

For an actual detection test, start a session and leave the preview controls alone. Open the camera view and check **Agent activity** to see what triggered each reminder.

## Settings and everyday use

You can change reminder intervals and enable or disable individual features in Settings. Save your changes and start a new session to apply them. Pause or end the session to release the webcam.

User settings are saved in `settings.json`, which is created locally and is not included in Git. A fresh checkout uses the defaults in `timer_settings.py`. Demo mode shortens intervals; saved settings can override the defaults on later launches.

Use **I drank** when a drink was missed, and **Undo automatic sip** when one was recorded incorrectly. Recalibrate after moving the camera or changing your seating position.

## How it works

OpenCV 5 handles camera processing, person and pose inference, object detection, and tracking. MediaPipe provides face landmarks. The session controller combines visual observations with timers, and a rule-based controller decides when to show a reminder or follow up.

The interface uses HTML, CSS, and JavaScript based on the team's Figma design. Tkinter and Pillow display the animated desktop reminders.

## Privacy and limits

Camera frames are processed on the computer and are not saved by the app. Session summaries and decision traces are stored locally in `sessions/`; the older camera preview writes diagnostic logs to `logs/`. Both folders are excluded from Git.

Posture is measured relative to your reference, and distance is estimated from changes in face size. Neither is a medical measurement. Drinking detection does not measure water volume or hydration. Eye and mouth cues can suggest a break, but do not establish that someone is tired. The session-limit reminder does not detect sleep.

Optional meeting detection uses Windows microphone-use metadata, without recording audio. It can be wrong and is off by default. Straw assistance is also experimental and off by default.

## Project files

| File or folder | Purpose |
| --- | --- |
| `sora_ui.py` | Starts the local dashboard |
| `session_controller.py` | Session state and feature coordination |
| `companion_agent.py`, `agent_policy.py` | Reminder decisions and follow-up |
| `drinking_auto.py`, `vessel_*.py` | Drinking observations and container tracking |
| `web/` | Dashboard pages, styles, fonts, and logo |
| `assets/animations/` | CAMY animations |
| `models/`, `vendor/` | Model files, adapters, and license notices |
| `evaluation/` | Notes for checking behavior and evaluating recorded video |

The `test_*.py` files cover individual parts of the application. `pose_test.py` and the shorter **Start Sora** launchers are the earlier camera-preview entry points; use the UI launchers for the dashboard.

## Development checks

```powershell
.\.venv\Scripts\python.exe -B -m unittest test_ui test_timers test_visual_features test_agent test_delivery -q
.\.venv\Scripts\python.exe -B replay_agent.py
```

The replay uses synthetic observations to check decision behavior. It does not measure webcam accuracy. See [evaluation notes](evaluation/README.md) for tests using your own annotated video. No camera accuracy score is claimed for the current build.

## Models and credits

The interface, logo, and CAMY animations were created by our team. Model sources and adapter notes are listed in [MODEL_SOURCES.md](MODEL_SOURCES.md). Third-party license notices are kept in `vendor/` and `web/assets/fonts/`.
