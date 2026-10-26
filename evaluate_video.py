"""Read a consented local video through the real model pipeline; never open webcam."""
from pathlib import Path
import argparse,csv,hashlib,json,statistics,time


def score_events(predictions, intervals, tolerance=2.):
    matched=set();tp=0;fp=0;latencies=[]
    for instant in sorted(predictions):
        choices=[i for i,(start,end) in enumerate(intervals) if i not in matched and start<=instant<=end+tolerance]
        if choices:
            index=min(choices,key=lambda i:abs(instant-intervals[i][1]));matched.add(index);tp+=1
            latencies.append(instant-intervals[index][1])
        else:fp+=1
    fn=len(intervals)-tp
    return {'true_positive':tp,'false_positive_including_duplicates':fp,'false_negative':fn,
            'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
            'completion_offset_seconds':latencies}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video',type=Path);parser.add_argument('--labels',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path('evaluation/video_result.json'))
    parser.add_argument('--straw',action='store_true')
    parser.add_argument('--synthetic',action='store_true',help='Label a generated test clip honestly; not camera accuracy')
    args=parser.parse_args()
    if not args.video.is_file():parser.error('Video does not exist')
    labels=[]
    with args.labels.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=['start_seconds','end_seconds']:parser.error('Labels need start_seconds,end_seconds columns')
        for row in reader:
            start,end=float(row['start_seconds']),float(row['end_seconds'])
            if not 0<=start<=end:parser.error('Invalid annotation interval')
            labels.append((start,end))
    import cv2
    from face_vision import FaceVision
    from drinking_auto import DrinkingAuto
    from vendor.mp_persondet import MPPersonDet
    from vendor.mp_pose import MPPose
    from pose_tracking import infer_landmarks
    from pose_test import get_visible_points
    from calibration import PostureCalibration
    from posture_state import PostureState
    from posture_reminder import PostureReminder
    from session_controller import SessionController
    from timer_settings import load_settings
    root=Path(__file__).resolve().parent
    if cv2.__version__.split('.')[0]!='5':raise RuntimeError('OpenCV 5 required')
    capture=cv2.VideoCapture(str(args.video))
    if not capture.isOpened():raise RuntimeError('Cannot read video')
    fps=capture.get(cv2.CAP_PROP_FPS)
    if not 1<=fps<=240:raise RuntimeError('Video needs a valid frame rate')
    face=FaceVision(root/'models/face_landmarker.task');drink=DrinkingAuto(root);drink.straw_enabled=args.straw
    person=MPPersonDet(modelPath=str(root/'models/person_detection_mediapipe_2023mar.onnx'),scoreThreshold=.5,nmsThreshold=.3)
    pose=MPPose(modelPath=str(root/'models/pose_estimation_mediapipe_2023mar.onnx'),confThreshold=.8)
    controller=SessionController(root,load_settings(root/'settings.json',True),demo=True,persist=False)
    controller.start();controller.agent.cloud.config={} # Evaluation is reproducible and never transmits data.
    state=PostureState();reminder=PostureReminder(window_seconds=20);reference=None;samples=[]
    frame_count=0;known=0;face_frames=0;predictions=[];latencies=[];observations=[]
    began=time.perf_counter()
    try:
        while True:
            ok,frame=capture.read()
            if not ok:break
            t=frame_count/fps;frame_count+=1;clock=time.perf_counter();h,w=frame.shape[:2]
            bright=float(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY).mean());people=person.infer(frame) if bright>=35 else []
            points={}
            if len(people)==1:
                lm,_=infer_landmarks(frame,people,person,pose)
                if lm is not None:points=get_visible_points(lm,w,h)
            features=PostureCalibration.extract_features(points,w,h)
            facial=face.infer(frame,t) if bright>=35 and len(people)<=1 else None
            face_frames+=int(facial is not None)
            # First three seconds must be a user-verified neutral reference.
            if t<3 and features:samples.append(features)
            if t>=3 and reference is None and len(samples)>=8:
                reference={k:statistics.median(v[k] for v in samples) for k in samples[0]}
            posture=state.update(features,reference,now=t);known+=int(posture!='UNKNOWN')
            controller.observe(t,len(people)==1,posture,bright,False)
            controller.timers.set_posture(reminder.update(posture,now=t)=='REMIND' or reminder.alert_active)
            if drink.update(frame,facial,t,allowed=bright>=35 and len(people)<=1):
                predictions.append(t);controller.record_drink(automatic=True)
            controller.drinking_status=drink.label;controller.notice()
            observations.append({'seconds':round(t,3),'posture':posture,'face':facial is not None,'container':drink.box is not None,'sip_state':drink.cycle.phase})
            latencies.append(time.perf_counter()-clock)
    finally:capture.release();face.close()
    elapsed=time.perf_counter()-began
    if not frame_count:raise RuntimeError('Video contains no readable frames')
    if any(end>frame_count/fps for _,end in labels):raise ValueError('An annotation exceeds video duration')
    if any(labels[i][0]<labels[i-1][1] for i in range(1,len(labels))):raise ValueError('Annotations must be ordered and non-overlapping')
    result={'data_type':'synthetic_video_pipeline_test' if args.synthetic else 'real_video_with_user_supplied_annotations','opencv':cv2.__version__,
            'video_sha256':hashlib.sha256(args.video.read_bytes()).hexdigest(),'straw_assist':args.straw,
            'frames':frame_count,'video_seconds':frame_count/fps,'processing_fps':frame_count/elapsed,
            'median_pipeline_ms':statistics.median(latencies)*1000,'p95_pipeline_ms':sorted(latencies)[min(len(latencies)-1,int(.95*len(latencies)))]*1000,
            'face_coverage':face_frames/frame_count,'posture_known_coverage':known/frame_count,
            'calibration_available':reference is not None,'predicted_sips_seconds':predictions,
            'metrics':score_events(predictions,labels),'limitations':'Offline throughput, not live camera FPS. Labels require human review. No ingestion or medical ground truth.'}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2))
    args.out.with_suffix('.observations.jsonl').write_text('\n'.join(json.dumps(v) for v in observations))
    args.out.with_suffix('.agent.jsonl').write_text('\n'.join(json.dumps(v) for v in controller.agent.rows))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
