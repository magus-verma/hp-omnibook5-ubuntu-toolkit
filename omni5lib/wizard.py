"""A short, interactive front door; privileged work stays in the install command."""
import json
import os
from pathlib import Path
import subprocess

from .core import RepairError, hardware
from .repair import make_plan

def setup():
    if os.geteuid() == 0: raise RepairError('Run ./omni5 setup as your desktop user. It requests sudo only for installation.')
    plan = make_plan(hardware())
    print('HP OmniBook 5 Ubuntu setup')
    print(json.dumps(plan, indent=2))
    print('\nA preserved Windows installation or copy of its DriverStore is required.')
    print('1: Windows partition (tool mounts read-only; BitLocker clear-key only)')
    print('2: An already accessible Windows root directory')
    choice = input('Choose 1 or 2: ').strip()
    if choice not in ('1', '2'): raise RepairError('No source selected; nothing changed.')
    source = input('Windows partition path (/dev/...) or root directory path: ').strip()
    if not source: raise RepairError('No source entered; nothing changed.')
    print('The toolkit will install firmware overrides, an HP audio profile and a separate GRUB entry.')
    print('It keeps your recovered kernel/initrd/DTB and current default. It does not reboot.')
    if input('Type INSTALL to proceed, or anything else to cancel: ').strip() != 'INSTALL':
        print('Cancelled; nothing changed.'); return
    launcher = Path(__file__).resolve().parent.parent/'omni5'
    flag = '--windows-device' if choice == '1' else '--windows-root'
    result = subprocess.run(['sudo', '/usr/bin/python3', str(launcher), 'install', flag, str(Path(source).absolute())])
    if result.returncode: raise RepairError('Installation did not finish; read the error above. Do not select a new boot image.')
    print('\nOptional: ./omni5 shortcuts (Windows/Super + F-row)')
    print('Save work, reboot manually, select the toolkit firmware boot, then run ./omni5 verify.')
    print('Only after physical checks pass: sudo ./omni5 finalize --confirm-working')
