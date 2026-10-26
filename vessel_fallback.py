"""A second object model for vessels missed by NanoDet; all inference stays local."""
import cv2
import numpy as np
from vendor.yolox_upstream import YoloX

class VesselFallback(YoloX):
    def detect(self,frame):
        h,w=frame.shape[:2];ratio=min(640/w,640/h)
        canvas=np.full((640,640,3),114,np.float32)
        nw,nh=int(w*ratio),int(h*ratio)
        canvas[:nh,:nw]=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),(nw,nh))
        items=[]
        for row in self.infer(canvas):
            cls=int(row[5])
            if cls not in (39,40,41):continue
            box=row[:4]/ratio;box[[0,2]]=np.clip(box[[0,2]],0,w-1);box[[1,3]]=np.clip(box[[1,3]],0,h-1)
            if min(box[2:]-box[:2])<16:continue
            items.append({'box':box,'label':{39:'bottle',40:'glass',41:'cup'}[cls],'score':float(row[4])})
        return items
