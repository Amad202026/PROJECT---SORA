# Sora - AI Work Companion

## Elevator pitch
A local vision companion that notices posture changes and work habits, offers gentle animated reminders, and adapts its next action to observed recovery and your choices.

## Inspiration
People can become absorbed in computer work and overlook their posture, water
breaks and time away from the desk. We wanted a companion that responds to what
it can actually observe and respects what it cannot know. The team designed the
Figma interface and six original character animations around that interaction.

## What it does
Sora compares head and shoulder measurements with a personal reference. It
combines sustained posture changes with configurable water, movement, screen-break
and session-limit reminders. Cup and bottle motion can estimate a likely sip;
users can correct missed or incorrect records. Relative face size, prolonged
eye closure and repeated possible yawns provide additional experimental cues.

One transparent character appears above one English caption with dismiss,
acknowledge and snooze controls. A deterministic agent observes the outcome:
recovery closes the goal, missing evidence pauses the intervention, and an
unresolved posture/distance goal can produce one alternative break offer.
Opt-in microphone-use metadata can defer reminders during a possible meeting.

## How we built it
OpenCV 5 runs substantive person, pose and vessel inference, tracking and
image processing locally. MediaPipe face landmarks complement this pipeline.
Python manages session state and a local HTTP interface derived from the team's
Figma design; Tk displays the transparent GIF reminders. The agent records
structured observations, decisions, tool calls and outcomes in local JSONL traces.

An optional IAM-authenticated AWS Lambda implements the intervention policy.
Only derived decision flags leave the device. The desktop constrains actions and
falls back locally on cloud failure. **Deployment is prepared but has not yet
been verified in an AWS account. Replace this paragraph with the actual region,
deployment receipt and successful AWS trace after deployment; do not submit an
unverified cloud claim.**

## Challenges we ran into
Vessels can cover the mouth, pose landmarks can disappear during a sip, and a
container near a face does not prove drinking. We added temporal approach/contact/
retreat checks, bounded occlusion bridging, alternative detector views, a fallback
detector, duplicate suppression and manual undo. A geometric straw helper remains
experimental and is off by default. Meeting metadata can also be ambiguous.

## Accomplishments
We implemented an integrated prototype with personal posture calibration,
transparent animated reminders, human controls and outcome-aware agent traces.
The current release passes 75 automated tests and six synthetic agent scenarios.
The UI was exercised in a local browser. These results verify program behavior;
they are not a measured real-camera accuracy claim.

## What we learned
A useful intervention needs reliable timing, explicit uncertainty and a way to
verify its outcome. Unknown tracking must never be treated as recovery, and a
dismiss action must not be interpreted as successful behavior change.

## What's next
Complete real-video evaluation across vessel types, lighting and participants;
verify AWS deployment; improve vessel occlusion and straw handling from measured
failure cases. This application does not diagnose dehydration, fatigue, sleep
disorders or ergonomic injury, and it does not measure fluid volume.

## Built with
Python, OpenCV 5, NumPy, MediaPipe, Pillow, Tkinter, HTML, CSS, JavaScript, Figma,
AWS Lambda, AWS CloudFormation, AWS IAM, Amazon CloudWatch.
Only list AWS as deployed technology after completing the actual deployment.

## Testing instructions (paste after adding distribution links)
Download and extract the complete Sora 1.7 archive into a new folder on Windows.
Install Python 3.14, run Setup Sora UI.bat, then Start Sora UI Demo.bat. Models and
animation assets are included. Start a session and calibrate with your head and
shoulders visible. Demo timers are shortened and clearly labelled. Compare a
sustained lower-head position with a return to reference; inspect Agent activity.
Test dismiss, snooze, Pause/End, water confirmation and automatic-sip undo.
Run the supplied automated tests and replay_agent.py for reproducible logic checks.
Use the evaluator and your own reviewed annotations for camera accuracy.
A live screen-share can demonstrate the webcam/desktop overlay; the local UI
is not a public website. Provide judges with a real arranged time and contact.

## Final fields requiring the team
- Team member names and roles; team appearance in the demo video.
- Judge-accessible archive/repository URL and video URL (maximum five minutes).
- Actual AWS deployment evidence and real-video results, including failures.
- A live demonstration arrangement if no working public endpoint is provided.

Official requirements and award rubric (checked 26 October 2026):
https://opencv26.devpost.com/ and https://opencv26.devpost.com/rules
The page header lists 26 October 2026, 11:45 pm PDT (27 October, 14:45 WITA).
The body lists a later time; use the earlier header deadline and verify the form.
