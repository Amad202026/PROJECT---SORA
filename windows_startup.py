"""Opt-in startup registration. Called only after the user saves the switch."""
from pathlib import Path
import os,subprocess,sys

def set_startup(enabled, root):
    if os.name!='nt':
        if enabled:raise ValueError('Start with Windows requires Windows.')
        return
    import winreg
    name='SoraWorkCompanion'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        if enabled:
            pythonw=Path(sys.executable).with_name('pythonw.exe')
            if not pythonw.is_file():raise ValueError('pythonw.exe is unavailable. Run Setup Sora UI first.')
            command=subprocess.list2cmdline([str(pythonw),str(Path(root).resolve()/'sora_ui.py')])
            winreg.SetValueEx(key,name,0,winreg.REG_SZ,command)
        else:
            try:winreg.DeleteValue(key,name)
            except FileNotFoundError:pass
