"""One English popup for reminders; repeated frames do not reopen a notice."""
import tkinter as tk
from wellness_timers import duration


class ReminderCenter:
    def __init__(self, engine):
        self.engine=engine;self.visible_key=None
        self.root=tk.Tk();self.root.withdraw();self.root.title('Sora - Reminder')
        self.root.configure(bg='#17202b');self.root.resizable(False,False);self.root.attributes('-topmost',True)
        self.root.protocol('WM_DELETE_WINDOW',self.dismiss)
        self.title=tk.Label(self.root,font=('Segoe UI',18,'bold'),fg='white',bg='#17202b',wraplength=480)
        self.title.pack(padx=24,pady=(24,12))
        self.body=tk.Label(self.root,font=('Segoe UI',11),fg='#dce5ef',bg='#17202b',wraplength=470,justify='center')
        self.body.pack(padx=24,pady=(0,18))
        self.actions=tk.Frame(self.root,bg='#17202b');self.actions.pack(padx=16,pady=(0,20))

    def dismiss(self):
        if self.visible_key:self.engine.dismiss(self.visible_key[0])
        self.hide()

    def hide(self):self.root.withdraw();self.visible_key=None

    def act(self, action, kind):
        if action=='snooze':self.engine.snooze(kind)
        elif action=='break':self.engine.start_break()
        elif action=='resume':self.engine.resume_break()
        elif action=='end':self.engine.request_exit=True
        elif action=='drink':self.engine.reset_timer('water','user_reported_drink')
        elif action=='move':self.engine.reset_timer('movement','user_reported_movement')
        else:self.engine.dismiss(kind)
        self.hide()

    def content(self,kind):
        return {
            'water':('Time for a water break','Your water-reminder interval has elapsed. Consider having a drink. Automatic drinking detection is paused.', [('I drank','drink')]),
            'movement':('Time to move','Your observed-session interval since your last movement record has elapsed. Consider standing or stretching when convenient.', [('I moved','move'),('Start break','break')]),
            'eyes':('Time for a screen break','Your observed-session interval has elapsed. Consider looking away and taking a break. This timer does not measure eye strain or gaze.', [('Start break','break')]),
            'sleep':('Consider ending this work session','You have reached your configured observed-session limit. Consider resting and ending the session. Sora cannot determine whether you need sleep.', [('End session','end')]),
            'posture':('Time to check your posture','Your head position has stayed lower than your calibrated reference. Consider adjusting your sitting position.', []),
            'dark_camera':('Camera view is too dark','Improve the lighting or check whether the camera is covered. Observed-time counting is paused until the view is usable.', []),
            'break_done':('Your break timer has finished','Resume when you are ready. Sora has measured the timer, not verified that you rested.', [('Resume','resume')]),
        }[kind]

    def pump(self):
        key=self.engine.notice()
        if key is None:self.hide()
        elif key!=self.visible_key:
            self.visible_key=key;kind=key[0]
            for widget in self.actions.winfo_children():widget.destroy()
            title,body,buttons=self.content(kind)
            if kind=='eyes':body+=f" Planned break: {duration(self.engine.config['break_seconds'])}."
            self.title.config(text=title);self.body.config(text=body)
            if kind in ('water','movement','eyes','posture','sleep'):
                buttons=buttons+[('Snooze','snooze')]
            if kind!='break_done':buttons=buttons+[('Dismiss','dismiss')]
            for label,action in buttons:
                tk.Button(self.actions,text=label,font=('Segoe UI',10),padx=10,pady=6,
                          command=lambda a=action,k=kind:self.act(a,k)).pack(side='left',padx=4)
            self.root.update_idletasks()
            width,height=self.root.winfo_reqwidth(),self.root.winfo_reqheight()
            x=max(0,(self.root.winfo_screenwidth()-width)//2);y=max(0,(self.root.winfo_screenheight()-height)//2)
            self.root.geometry(f'{width}x{height}+{x}+{y}');self.root.deiconify();self.root.lift()
            self.engine.logger.write('notice_shown',kind=kind)
        self.root.update_idletasks();self.root.update()

    def close(self):self.root.destroy()
