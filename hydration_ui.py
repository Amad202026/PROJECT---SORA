"""A single Tk root arbitrates posture and hydration notices."""
import tkinter as tk


class ReminderCenter:
    def __init__(self, on_dismiss=None, hydration=None):
        self.on_dismiss = on_dismiss
        self.hydration = hydration
        self.posture_active = False
        self.posture_dismissed = False
        self.water_active = False
        self.water_dismissed = False
        self.water_record_count = hydration.clock.count if hydration else 0
        self.pending = None
        self.suspended = False
        self.visible_key = None
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title('Sora - Reminder')
        self.root.configure(bg='#17202b')
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)
        self.root.protocol('WM_DELETE_WINDOW', self.dismiss)
        self.title = tk.Label(self.root, font=('Segoe UI', 19, 'bold'),
                              fg='white', bg='#17202b', wraplength=460)
        self.title.pack(padx=25, pady=(25, 12))
        self.body = tk.Label(self.root, font=('Segoe UI', 11), fg='#dce5ef',
                            bg='#17202b', wraplength=440, justify='center')
        self.body.pack(padx=25, pady=(0, 18))
        self.actions = tk.Frame(self.root, bg='#17202b')
        self.actions.pack(padx=20, pady=(0, 22))

    def show(self):
        if not self.posture_active:
            self.posture_dismissed = False
        self.posture_active = True

    def hide(self):
        self.posture_active = False
        self.posture_dismissed = False

    def set_hydration(self, due, pending, suspended=False):
        monitor = getattr(self, 'hydration', None)
        count = monitor.clock.count if monitor else 0
        if count != getattr(self, 'water_record_count', count):
            self.water_dismissed = False
        self.water_record_count = count
        self.water_active, self.pending, self.suspended = due, None, suspended

    def dismiss(self):
        if self.visible_key is None:
            return
        kind = self.visible_key[0]
        if kind == 'sip':
            self.hydration.reject()
            self.pending = None
        elif kind == 'posture':
            self.posture_dismissed = True
            if self.on_dismiss:
                self.on_dismiss()
        else:
            self.water_dismissed = True
            if self.hydration:
                self.hydration.logger.write('water_reminder_dismissed', timer_reset=False)
        self.visible_key = None
        self.root.withdraw()

    def confirm(self):
        if self.hydration:
            self.hydration.record('manual_confirmation')
        self.pending = None
        self.water_active = False
        self.visible_key = None
        self.root.withdraw()

    def pump(self):
        key = None
        if not self.suspended:
            if self.posture_active and not self.posture_dismissed:
                key = ('posture', 0)
            elif self.water_active and not self.water_dismissed:
                key = ('water', 0)
        if key is None:
            self.root.withdraw()
            self.visible_key = None
        elif key != self.visible_key:
            self.visible_key = key
            for button in self.actions.winfo_children():
                button.destroy()
            if key[0] == 'posture':
                title = 'Time to check your posture'
                body = ('Your head position has stayed lower than your reference for much '
                        'of the observation period.\n\nConsider adjusting your sitting position.')
            else:
                title = 'Time for a water break'
                body = ('No drinking event has been recorded during your reminder interval.\n\n'
                        'Consider taking a sip. If you already drank, confirm below.')
            self.title.config(text=title)
            self.body.config(text=body)
            if key[0] != 'posture':
                tk.Button(self.actions, text='I drank', command=self.confirm,
                          font=('Segoe UI', 11), padx=18, pady=6).pack(side='left', padx=8)
            tk.Button(self.actions, text='Dismiss',
                      command=self.dismiss, font=('Segoe UI', 11), padx=18, pady=6).pack(side='left', padx=8)
            self.root.update_idletasks()
            width, height = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
            x = max(0, (self.root.winfo_screenwidth() - width) // 2)
            y = max(0, (self.root.winfo_screenheight() - height) // 2)
            self.root.geometry(f'{width}x{height}+{x}+{y}')
            self.root.deiconify()
            self.root.lift()
        self.root.update_idletasks()
        self.root.update()

    def close(self):
        self.root.destroy()
