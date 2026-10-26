"""Opt-in Windows microphone-use heuristic. Never records audio or window text."""
import csv
import io
import os
import subprocess
from threading import Thread

APPS={'teams.exe','ms-teams.exe','zoom.exe','webex.exe','discord.exe','slack.exe',
      'chrome.exe','msedge.exe','firefox.exe','brave.exe'}


def microphone_app_active():
    if os.name!='nt':return None
    import winreg
    try:
        data=subprocess.run(['tasklist','/FO','CSV','/NH'], capture_output=True,text=True,timeout=3,
                            creationflags=subprocess.CREATE_NO_WINDOW,check=True).stdout
        running={row[0].lower() for row in csv.reader(io.StringIO(data)) if row}
        path=r'Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,path) as root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                name=winreg.EnumKey(root,i)
                executable=name.replace('#','/').split('/')[-1].lower()
                if executable not in APPS or executable not in running:continue
                with winreg.OpenKey(root,name) as key:
                    try:
                        start=winreg.QueryValueEx(key,'LastUsedTimeStart')[0]
                        stop=winreg.QueryValueEx(key,'LastUsedTimeStop')[0]
                        if start>0 and stop==0:return True
                    except FileNotFoundError:continue
        return False
    except (OSError,subprocess.SubprocessError):return None


class MeetingDetector:
    def __init__(self):
        self.active=False;self.candidate_since=None;self.release_since=None
        self.status='Automatic meeting detection off'

    def update(self, sample, now, enabled=True):
        if not enabled:
            self.active=False;self.candidate_since=self.release_since=None
            self.status='Automatic meeting detection off';return False
        if sample is None:
            # Do not preserve an old suppression indefinitely on permission errors.
            self.active=False;self.candidate_since=self.release_since=None
            self.status='Meeting signal unavailable; use Quiet mode';return False
        if sample:
            self.release_since=None
            if self.candidate_since is None:self.candidate_since=now
            if now-self.candidate_since>=10:self.active=True
        else:
            self.candidate_since=None
            if self.release_since is None:self.release_since=now
            if now-self.release_since>=45:self.active=False
        self.status='Possible meeting — reminders deferred' if self.active else 'No meeting signal'
        return self.active


class MeetingProbe:
    def __init__(self):self.sample=None;self.at=-999.;self.started=-999.;self.busy=False
    def poll(self, now, enabled):
        if not enabled:return False
        if not self.busy and now-self.started>=5:
            self.busy=True;self.started=now
            def read():
                import time
                try:self.sample=microphone_app_active();self.at=time.monotonic()
                finally:self.busy=False
            Thread(target=read,daemon=True).start()
        return self.sample if now-self.at<12 else None
