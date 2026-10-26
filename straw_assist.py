"""Experimental straight-straw geometry; disabled by default, not a straw model."""
import math
import cv2


def connects_mouth_to_vessel(line, mouth, box, scale):
    x1,y1,x2,y2=map(float,box);mx,my=mouth;ax,ay,bx,by=map(float,line)
    def inside(x,y):return x1<=x<=x2 and y1<=y<=y2
    if inside(mx,my) or (inside(ax,ay) and inside(bx,by)):return False
    length=math.hypot(ax-bx,ay-by)
    if not .05*scale<=length<=.65*scale:return False
    def at_vessel(x,y):return math.hypot(max(x1-x,0,x-x2),max(y1-y,0,y-y2))<=.06*scale
    return ((math.hypot(ax-mx,ay-my)<.06*scale and at_vessel(bx,by)) or
            (math.hypot(bx-mx,by-my)<.06*scale and at_vessel(ax,ay)))


class StrawAssist:
    def __init__(self):self.since=None;self.last=None
    def reset(self):self.since=None;self.last=None
    def observe(self, frame, face, box, now):
        if face is None or box is None:self.reset();return False
        if self.last is not None and now-self.last>1:self.reset()
        self.last=now;scale=face['scale'];mx,my=face['mouth'];h,w=frame.shape[:2]
        pad=.7*scale;x=max(0,int(mx-pad));y=max(0,int(my-pad));right=min(w,int(mx+pad));bottom=min(h,int(my+pad))
        if right-x<5 or bottom-y<5:self.reset();return False
        gray=cv2.cvtColor(frame[y:bottom,x:right],cv2.COLOR_BGR2GRAY)
        lines=cv2.HoughLinesP(cv2.Canny(gray,70,150),1,math.pi/180,15,minLineLength=max(8,.05*scale),maxLineGap=5)
        hit=False
        if lines is not None:
            for entry in lines[:80]:
                ax,ay,bx,by=entry[0]
                if connects_mouth_to_vessel((ax+x,ay+y,bx+x,by+y),face['mouth'],box,scale):hit=True;break
        if not hit:self.since=None;return False
        if self.since is None:self.since=now
        return now-self.since>=.4
