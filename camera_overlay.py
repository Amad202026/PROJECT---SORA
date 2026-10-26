"""Draw only visible upper-body landmarks on the mirrored camera preview."""
import cv2


def draw_tracking_overlay(frame, points, state, fps):
    height,width=frame.shape[:2]
    visible={i:(width-1-int(x),int(y)) for i,(x,y) in points.items() if 0<=x<width and 0<=y<height}
    color=(0,190,255) if state=='LOWER_HEAD_POSITION' else (80,230,140)
    if all(i in visible for i in (0,11,12)):
        nose,left,right=(visible[i] for i in (0,11,12))
        center=((left[0]+right[0])//2,(left[1]+right[1])//2)
        cv2.line(frame,left,right,color,2);cv2.line(frame,nose,center,color,2)
        xs=[v[0] for v in visible.values()];ys=[v[1] for v in visible.values()]
        x1=max(0,min(xs)-25);y1=max(0,min(ys)-35)
        x2=min(width-1,max(xs)+25);y2=min(height-1,max(ys)+40)
        cv2.rectangle(frame,(x1,y1),(x2,y2),color,2)
        cv2.putText(frame,'Upper body',(x1,max(15,y1-7)),cv2.FONT_HERSHEY_SIMPLEX,.45,color,1,cv2.LINE_AA)
    for index,point in visible.items():
        cv2.circle(frame,point,4,color,-1)
        name={0:'Nose',11:'Left shoulder',12:'Right shoulder'}.get(index,'')
        cv2.putText(frame,name,(max(0,min(width-110,point[0]+7)),max(18,point[1]-8)),cv2.FONT_HERSHEY_SIMPLEX,.4,color,1,cv2.LINE_AA)
    cv2.rectangle(frame,(0,height-28),(width,height),(22,25,32),-1)
    label=f'{state.replace("_"," ")} | {fps:.1f} FPS'
    cv2.putText(frame,label,(10,height-9),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1,cv2.LINE_AA)
