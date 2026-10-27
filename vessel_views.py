"""One extra detector view per inference, mapped back to camera coordinates."""
import cv2
import numpy as np


def map_box(box, matrix, width, height):
    x1,y1,x2,y2=box
    corners=np.array([[x1,y1,1],[x2,y1,1],[x2,y2,1],[x1,y2,1]],float)
    points=corners @ matrix.T
    result=np.r_[points.min(axis=0),points.max(axis=0)]
    result[[0,2]]=np.clip(result[[0,2]],0,width-1)
    result[[1,3]]=np.clip(result[[1,3]],0,height-1)
    return result


class VesselViews:
    def __init__(self, detector):
        self.detector=detector
        self.step=0

    def detect(self, frame):
        height,width=frame.shape[:2]
        detections=self.detector.detect(frame)
        mode=self.step % 4
        self.step+=1
        if mode==0:
            view=cv2.flip(frame,1)
            inverse=np.array([[-1,0,width-1],[0,1,0]],float)
        elif mode==1:
            view=frame[:int(height*.8)]
            inverse=np.array([[1,0,0],[0,1,0]],float)
        else:
            # Rotate the entire image; warpAffine on the original canvas clipped
            # bottles near the left/right edges of a landscape camera view.
            if mode==2:
                view=cv2.rotate(frame,cv2.ROTATE_90_CLOCKWISE)
                inverse=np.array([[0,1,0],[-1,0,height-1]],float)
            else:
                view=cv2.rotate(frame,cv2.ROTATE_90_COUNTERCLOCKWISE)
                inverse=np.array([[0,-1,width-1],[1,0,0]],float)
        for detection in self.detector.detect(view):
            item=dict(detection)
            item['box']=map_box(item['box'],inverse,width,height)
            if min(item['box'][2:]-item['box'][:2])>=8:
                detections.append(item)
        # NMS accepts x,y,width,height rather than x1,y1,x2,y2.
        if not detections:return []
        boxes=[np.r_[d['box'][:2],d['box'][2:]-d['box'][:2]].tolist() for d in detections]
        keep=cv2.dnn.NMSBoxes(boxes,[float(d['score']) for d in detections],.35,.4)
        return [detections[int(i)] for i in np.asarray(keep).reshape(-1)]
