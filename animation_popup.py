"""Transparent Windows reminders using the team's original GIFs."""
import json,time,threading
import tkinter as tk
from PIL import Image,ImageTk

ANIMATIONS={'agent_break':'Jeda','water':'Minum','posture':'Postur','distance':'Jarak','fatigue':'Ngantuk',
            'eyes':'Jeda','movement':'Jeda','break_done':'Jeda','sleep':'Tidur','dark_camera':'Ngantuk'}
CAPTIONS={
    'agent_break':'Your position hasn’t improved yet. Would a short break help?',
    'water':'Time for a sip of water.',
    'posture':'Your head has stayed lower. Try adjusting your posture.',
    'distance':'You’re closer than your reference. Try moving back a little.',
    'fatigue':'Your eye or mouth movements suggest a break may help.',
    'eyes':'You’ve been at your desk for a while. Give your eyes a break.',
    'movement':'Time to stand up and stretch.',
    'sleep':'You’ve reached your session limit. Time to rest.',
    'break_done':'Your break timer is finished. Ready to return?',
    'dark_camera':'It’s too dark to see clearly. Try adding some light.',
}
OK_HINT={'agent_break':'Start a break','water':'I drank','posture':'Acknowledge','distance':'Acknowledge',
         'fatigue':'Start a break','eyes':'Start a break','movement':'I moved',
         'sleep':'End session','break_done':'Resume','dark_camera':'Acknowledge'}

class GifPlayer:
    """Keep one decoded frame, not hundreds of full-resolution RGBA images."""
    def __init__(self,path,bbox):
        self.image=Image.open(path);self.bbox=bbox;self.index=0
    def frame(self):
        self.image.seek(self.index)
        duration=max(20,self.image.info.get('duration',40))
        frame=self.image.convert('RGBA').crop(self.bbox)
        frame.thumbnail((260,260),Image.Resampling.LANCZOS)
        # Windows color-key transparency has no partial alpha. Threshold only the
        # rendered copy to avoid a colored fringe; source GIFs remain unchanged.
        frame.putalpha(frame.getchannel('A').point(lambda a:255 if a>=128 else 0))
        self.index=(self.index+1)%self.image.n_frames
        return frame,duration
    def close(self):self.image.close()

class DesktopPopup:
    def __init__(self,app):
        self.app=app;self.root=tk.Tk();self.root.withdraw()
        self.root.title('Sora reminder');self.root.overrideredirect(True)
        self.root.attributes('-topmost',True)
        self.key='#090a0b';self.root.configure(bg=self.key)
        self.root.wm_attributes('-transparentcolor',self.key)
        self.canvas=tk.Canvas(self.root,width=420,height=400,bg=self.key,highlightthickness=0)
        self.canvas.pack();self.visible_key=None;self.player=None;self.photo=None;self.next_frame=0
        self.assets=app.root/'assets/animations'
        self.manifest=json.loads((self.assets/'manifest.json').read_text())
        self.root.bind('<Escape>',lambda e:self.act('dismiss'))
        self.root.bind('<Return>',self.enter)
        self.root.bind('<space>',lambda e:self.act('snooze'))
        self.root.bind('<Tab>',self.tab);self.focused=-1
        self.root.protocol('WM_DELETE_WINDOW',lambda:self.act('dismiss'))
        self.root.bind('<ButtonPress-1>',self.drag_start)
        self.root.bind('<B1-Motion>',self.drag)
        self.drag_origin=None
    def drag_start(self,event):
        self.drag_origin=(event.x_root-self.root.winfo_x(),event.y_root-self.root.winfo_y()) if event.y<320 else None
    def drag(self,event):
        if self.drag_origin:self.root.geometry(f'+{event.x_root-self.drag_origin[0]}+{event.y_root-self.drag_origin[1]}')
    def tab(self,event):
        self.focused=(self.focused+1)%3;self.tooltip(self.hints[self.focused]);return 'break'
    def enter(self,event):self.act(('dismiss','acknowledge','snooze')[self.focused] if self.focused>=0 else 'acknowledge')
    def tooltip(self,text):
        self.canvas.delete('hint');self.outlined_text(210,386,text,11,'hint')
    def outlined_text(self,x,y,text,size,tag,width=395):
        for dx,dy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
            self.canvas.create_text(x+dx,y+dy,text=text,font=('Segoe UI',size,'bold'),fill='#202025',width=width,justify='center',tags=tag)
        self.canvas.create_text(x,y,text=text,font=('Segoe UI',size,'bold'),fill='white',width=width,justify='center',tags=tag)
    def act(self,action):
        if not self.visible_key:return
        self.app.commands.put((action,{'kind':self.visible_key[0],'notice_id':self.visible_key[1]},{},threading.Event()))
        self.root.withdraw()
    def show(self,notice,preferences):
        if self.player:self.player.close()
        self.canvas.delete('all');self.focused=-1
        kind=notice[0];name=ANIMATIONS[kind]
        self.player=GifPlayer(self.assets/(name+'.gif'),self.manifest[name]['bbox'])
        self.animation=preferences.get('animation',True);self.next_frame=0
        self.canvas.create_image(210,140,anchor='center',tags='animation')
        self.outlined_text(210,298,CAPTIONS[kind],14,'caption')
        self.hints=['Dismiss',OK_HINT[kind],'Snooze']
        if notice[1]=='preview':self.hints=['Close preview']*3
        for i,x in enumerate((142,210,278)):
            tag=f'button{i}'
            self.canvas.create_rectangle(x-24,326,x+24,374,fill=self.key,outline='',tags=tag)
            self.outlined_text(x,350,('×','✓','Ⅱ')[i],26,tag)
            self.canvas.tag_bind(tag,'<Button-1>',lambda e,a=('dismiss','acknowledge','snooze')[i]:self.act(a))
            self.canvas.tag_bind(tag,'<Enter>',lambda e,t=self.hints[i]:self.tooltip(t))
            self.canvas.tag_bind(tag,'<Leave>',lambda e:self.canvas.delete('hint'))
        w,h=420,400;sw,sh=self.root.winfo_screenwidth(),self.root.winfo_screenheight()
        x,y=((sw-w)//2,(sh-h)//2) if preferences['position']=='center' else (sw-w-25,sh-h-70)
        self.root.geometry(f'{w}x{h}+{max(0,x)}+{max(0,y)}');self.root.deiconify()
        if preferences.get('sound'):self.root.bell()
    def pump(self):
        with self.app.lock:
            c=self.app.controller;notice=c.notice();preferences=c.preferences.copy()
        if notice!=self.visible_key:
            self.visible_key=notice
            if notice:self.show(notice,preferences)
            else:
                self.root.withdraw()
                if self.player:self.player.close();self.player=None
                self.photo=None
        if notice and self.player and time.monotonic()>=self.next_frame:
            frame,delay=self.player.frame();self.photo=ImageTk.PhotoImage(frame,master=self.root)
            self.canvas.itemconfigure('animation',image=self.photo)
            self.next_frame=time.monotonic()+delay/1000 if self.animation else float('inf')
        self.root.update_idletasks();self.root.update()
    def close(self):
        if self.player:self.player.close()
        self.root.destroy()
