"""Hardware checks, read-only extraction, and recoverable system changes."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request

TESTED_KERNEL = '7.2.2-jg-0-qcom-x1e'
FW_REL = Path('qcom/x1p42100/hp/omnibook-5')
FW_ROOT = Path('/usr/lib/firmware/updates')
STATE = Path('/var/lib/omni5')
DTB = Path('/boot/x1p42100-hp-omnibook-5.dtb')
BOARD_URL = 'https://github.com/user-attachments/files/25822586/board-2.bin.zst.txt'
BOARD_SHA = 'dd17d8aaccdc3e8a0a82d0fd6858934d7c87cfc10c2658cfbb570e604d692afc'
BOARD_ID = b'bus=pci,vendor=17cb,device=1103,subsystem-vendor=103c,subsystem-device=8d9a,qmi-chip-id=18,qmi-board-id=255'
BOARD_REL = Path('ath11k/WCN6855/hw2.1/board-2.bin')
TOPOLOGY_REL = Path('qcom/x1e80100/X1P42100-HP-OMNIBOOK-5-tplg.bin.zst')
TOPOLOGY_SOURCE = Path('/usr/lib/firmware/qcom/x1e80100/X1E80100-Romulus-tplg.bin.zst')
GPU_MICROCODE = ['qcom/gen71500_sqe.fw', 'qcom/gen71500_gmu.bin']
FIRMWARE_GROUPS = {
    'qcsubsys_ext_adsp8380.inf_arm64_': ['qcadsp8380.mbn', 'adsp_dtbs.elf', 'adspr.jsn', 'adsps.jsn', 'adspua.jsn', 'battmgr.jsn'],
    'qcnspmcdm_ext_cdsp8380.inf_arm64_': ['qccdsp8380.mbn', 'cdsp_dtbs.elf', 'cdspr.jsn'],
    'qcdx8380.inf_arm64_': ['qcdxkmsucpurwa.mbn'],
}
ENTRY = Path('/etc/grub.d/99_omnibook5_toolkit')
MENU = Path('/etc/default/grub.d/99-omnibook5-toolkit.cfg')
HOOK = Path('/etc/initramfs-tools/hooks/omnibook5-toolkit')
HP_UCM = Path('/usr/share/alsa/ucm2/Qualcomm/x1e80100/HP-OmniBook5-Toolkit.conf')
BOOT_ID = 'omnibook5-toolkit'
BOOT_TITLE = 'HP OmniBook 5 - toolkit firmware boot'

class RepairError(RuntimeError):
    pass

def run(args, *, check=True, timeout=180, env=None):
    try:
        p = subprocess.run([str(a) for a in args], text=True, capture_output=True,
                           timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RepairError(f'{args[0]}: {e}') from e
    if check and p.returncode:
        raise RepairError(f'{args[0]} failed ({p.returncode}):\n{(p.stdout+p.stderr)[-4000:]}')
    return p

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def text(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return ''

def supported_model(model):
    return bool(re.fullmatch(r'HP OmniBook 5 Laptop 16-bf\S*', model))

def hardware():
    pci = []
    for d in Path('/sys/bus/pci/devices').glob('*'):
        if text(d / 'vendor') == '0x17cb' and text(d / 'device') == '0x1103':
            pci.append({'vendor': text(d/'vendor'), 'device': text(d/'device'),
                        'subsystem_vendor': text(d/'subsystem_vendor'), 'subsystem_device': text(d/'subsystem_device')})
    fw_names = set()
    base = Path('/sys/firmware/devicetree/base')
    if base.exists():
        for p in base.rglob('firmware-name'):
            try:
                fw_names.update(x.decode() for x in p.read_bytes().split(b'\0') if x)
            except (OSError, UnicodeError):
                continue
    os_info = {}
    for line in text('/etc/os-release').splitlines():
        if '=' in line:
            k, v = line.split('=', 1); os_info[k] = v.strip('"')
    board_ids = set()
    if shutil.which('journalctl'):
        logs = run(['journalctl', '-k', '-b', '--no-pager', '-o', 'cat'], check=False, timeout=30).stdout
        for match in re.finditer(r'ath11k_pci[^\n]*chip_id (0x[0-9a-f]+)[^\n]*board_id (0x[0-9a-f]+)', logs, re.I):
            board_ids.add((int(match[1], 16), int(match[2], 16)))
    return {'model': text('/sys/class/dmi/id/product_name'), 'architecture': platform.machine(),
            'kernel': platform.release(), 'os': os_info.get('ID'), 'os_version': os_info.get('VERSION_ID'),
            'wifi_hardware': pci, 'wifi_board_ids': sorted(board_ids), 'dt_firmware_names': sorted(fw_names)}

def validate_hardware(h):
    errors = []
    if not supported_model(h['model']): errors.append('Unsupported HP model; no system changes allowed.')
    if h['architecture'] != 'aarch64' or h['os'] != 'ubuntu': errors.append('Requires Ubuntu on ARM64.')
    if h['os_version'] != '26.04': errors.append('This release only supports the tested Ubuntu 26.04 userspace.')
    if h['kernel'] != TESTED_KERNEL: errors.append(f'Requires the tested {TESTED_KERNEL} kernel. See installation guide; this tool never upgrades kernels.')
    expected = {'vendor': '0x17cb', 'device': '0x1103', 'subsystem_vendor': '0x103c', 'subsystem_device': '0x8d9a'}
    if expected not in h['wifi_hardware']: errors.append('Wi-Fi subsystem differs from the verified board descriptor.')
    if h.get('wifi_board_ids') != [(18, 255)]: errors.append('Cannot verify the exact Wi-Fi chip/board ID (18/255) from this boot journal. Review hardware or journal access before installation.')
    required = {str(FW_REL / n) for n in ['qcadsp8380.mbn', 'adsp_dtbs.elf', 'qccdsp8380.mbn', 'cdsp_dtbs.elf', 'qcdxkmsucpurwa.mbn']}
    if not required.issubset(h['dt_firmware_names']): errors.append('Running device tree does not request the supported OmniBook 5 firmware paths.')
    if errors: raise RepairError('\n'.join(errors))

def doctor():
    h = hardware()
    try:
        validate_hardware(h); h['supported'] = True
    except RepairError as e:
        h['supported'] = False; h['unsupported_reason'] = str(e)
    h['audio_cards'] = text('/proc/asound/cards')
    h['remote_processors'] = {p.parent.name: text(p) for p in Path('/sys/class/remoteproc').glob('remoteproc*/state')}
    h['backlight_devices'] = [p.name for p in Path('/sys/class/backlight').glob('*')]
    h['keyboard_backlight_exposed'] = any('kbd_backlight' in p.name for p in Path('/sys/class/leds').glob('*'))
    h['boot_marker'] = next((x.split('=', 1)[1] for x in text('/proc/cmdline').split() if x.startswith('omni5_test=')), None)
    if shutil.which('glxinfo'):
        out = run(['glxinfo', '-B'], check=False, timeout=15).stdout
        h['graphics'] = {'accelerated': 'Accelerated: yes' in out, 'renderer': next((x.split(':', 1)[1].strip() for x in out.splitlines() if x.startswith('OpenGL renderer string:')), 'unavailable')}
    else:
        h['graphics'] = {'accelerated': None, 'renderer': 'Install mesa-utils and run doctor from the desktop session.'}
    if shutil.which('nmcli'):
        # Device/state only: never expose SSIDs, addresses, or credentials in a shareable report.
        env = dict(os.environ, LC_ALL='C')
        # Interface names such as enx... can embed a MAC, so omit names too.
        h['network_devices'] = run(['nmcli', '-t', '-f', 'TYPE,STATE', 'device'], check=False, env=env).stdout.strip().splitlines()
    h['failed_services'] = run(['systemctl', '--failed', '--no-pager', '--plain'], check=False).stdout.strip()
    return h

def hp_sound_card(cards):
    for line in cards.splitlines():
        if 'X1P42100-HP-OMNIBOOK-5' in line:
            match = re.match(r'\s*(\d+)\s+\[', line)
            if match: return 'hw:'+match.group(1)
    raise RepairError('The HP OmniBook 5 ALSA sound card is missing.')

def version_from_inf(path):
    b = path.read_bytes()
    content = b.decode('utf-16' if b.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig', errors='replace')
    m = re.search(r'^\s*DriverVer\s*=\s*(\d{1,2})/(\d{1,2})/(\d{4}),\s*([\d.]+)', content, re.M | re.I)
    if not m: raise RepairError(f'Missing DriverVer in {path.name}')
    month, day, year, version = m.groups()
    return (int(year), int(month), int(day), tuple(int(n) for n in version.split('.')))

def select_firmware(windows_root):
    store = Path(windows_root).resolve() / 'Windows/System32/DriverStore/FileRepository'
    if not store.is_dir(): raise RepairError('Windows DriverStore not found. Supply its Windows root or use the read-only device option.')
    result = {}
    for prefix, names in FIRMWARE_GROUPS.items():
        candidates = []
        for folder in store.glob(prefix + '*'):
            if folder.is_symlink() or not folder.is_dir(): continue
            if all((folder / n).is_file() and not (folder / n).is_symlink() for n in names):
                versions = [version_from_inf(p) for p in folder.glob('*.inf') if not p.is_symlink()]
                if versions: candidates.append((max(versions), folder))
        if not candidates: raise RepairError(f'Complete local firmware set missing: {prefix}')
        version, folder = max(candidates, key=lambda x: (x[0], x[1].name))
        for name in names:
            p = folder / name
            if name.endswith('.jsn'):
                data = json.loads(p.read_text())
                if not isinstance(data.get('sr_domain'), dict): raise RepairError(f'Invalid PD metadata: {name}')
            else:
                with p.open('rb') as f:
                    if f.read(4) != b'\x7fELF': raise RepairError(f'Expected ELF firmware: {name}')
            result[name] = {'path': p, 'driver_version': version}
    return result

@contextmanager
def readonly_windows(device):
    device = Path(device).resolve()
    if not str(device).startswith('/dev/') or not device.is_block_device(): raise RepairError('Expected a Windows block device under /dev.')
    kind = run(['blkid', '-s', 'TYPE', '-o', 'value', device]).stdout.strip().lower()
    if kind not in ('bitlocker', 'ntfs'): raise RepairError('Only NTFS/BitLocker Windows partitions are supported.')
    base = Path(tempfile.mkdtemp(prefix='omni5-', dir='/run')); base.chmod(0o700)
    windows = base/'windows'; windows.mkdir(); unlocked = base/'unlocked'; unlocked.mkdir()
    unlocked_ok = mounted = False
    try:
        source = device
        if kind == 'bitlocker':
            p = run(['dislocker', '--readonly', '--clearkey', '--volume', device, '--', unlocked], check=False)
            if p.returncode:
                raise RepairError('BitLocker is not clear-key accessible. Unlock it interactively read-only, then supply --windows-root. No recovery key is saved or accepted on a command line by this toolkit.')
            unlocked_ok = True; source = unlocked/'dislocker-file'
        options = 'loop,ro,norecover' if kind == 'bitlocker' else 'ro,norecover'
        run(['mount', '-t', 'ntfs-3g', '-o', options, source, windows]); mounted = True
        yield windows
    finally:
        if mounted: run(['umount', windows])
        if unlocked_ok: run(['umount', unlocked])
        # Never recursively remove a mountpoint: an unmount failure must leave it intact.
        windows.rmdir(); unlocked.rmdir(); base.rmdir()

def validate_board(path):
    if sha(path) != BOARD_SHA or BOARD_ID not in Path(path).read_bytes():
        raise RepairError('Wi-Fi board checksum or exact hardware tuple mismatch.')

def obtain_board(directory, supplied=None):
    out = Path(directory)/'board-2.bin'
    if supplied:
        shutil.copyfile(supplied, out)
    else:
        compressed = Path(directory)/'board-2.bin.zst'
        with urllib.request.urlopen(BOARD_URL, timeout=30) as response, compressed.open('wb') as f:
            total = 0
            while chunk := response.read(1024*1024):
                total += len(chunk)
                if total > 20*1024*1024: raise RepairError('Unexpectedly large board download.')
                f.write(chunk)
        with out.open('wb') as f:
            p = subprocess.run(['zstd', '-d', '-c', str(compressed)], stdout=f, stderr=subprocess.PIPE, timeout=30)
        if p.returncode: raise RepairError('Board decompression failed.')
    validate_board(out)
    return out

class Transaction:
    def __init__(self, root=STATE):
        root = Path(root); root.mkdir(parents=True, exist_ok=True); root.chmod(0o700)
        self.directory = root / (time.strftime('%Y%m%d-%H%M%S')+'-'+os.urandom(3).hex())
        self.directory.mkdir(mode=0o700); self.changes = []; self.paths = set()
        self.save()
    def save(self):
        temporary = self.directory/'changes.tmp'
        with temporary.open('w') as f:
            f.write(json.dumps(self.changes, indent=2)+'\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temporary, self.directory/'changes.json')
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    def preserve(self, path):
        p = Path(path)
        if str(p) in self.paths: return
        if p.is_dir(): raise RepairError(f'Refusing to replace directory {p}')
        x = {'path': str(p), 'existed': p.exists() or p.is_symlink(), 'index': len(self.changes), 'symlink': p.is_symlink()}
        if x['existed']:
            if x['symlink']: x['link_target'] = os.readlink(p)
            else:
                old = self.directory/f"old-{x['index']}"; shutil.copy2(p, old)
                with old.open('rb') as f: os.fsync(f.fileno())
        self.changes.append(x); self.paths.add(str(p)); self.save()
    def write(self, path, data, mode=0o644):
        p = Path(path); self.preserve(p); p.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.omni5-', dir=p.parent)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data.encode() if isinstance(data, str) else data); f.flush(); os.fsync(f.fileno())
            os.chmod(name, mode); os.replace(name, p)
        finally:
            Path(name).unlink(missing_ok=True)
    def copy(self, source, target, mode=0o644): self.write(target, Path(source).read_bytes(), mode)
    def symlink(self, source, target):
        p = Path(target); self.preserve(p); p.parent.mkdir(parents=True, exist_ok=True)
        name = p.parent/('.omni5-link-'+os.urandom(8).hex())
        try:
            name.symlink_to(source); os.replace(name, p)
        finally: name.unlink(missing_ok=True)
    def remove(self, path): self.preserve(path); Path(path).unlink(missing_ok=True)
    def rollback(self): restore_transaction(self.directory)

def restore_transaction(directory):
    directory = Path(directory)
    for x in reversed(json.loads((directory/'changes.json').read_text())):
        p = Path(x['path'])
        if p.exists() or p.is_symlink(): p.unlink()
        if x['existed']:
            if x['symlink']: p.symlink_to(x['link_target'])
            else: shutil.copy2(directory/f"old-{x['index']}", p)
    os.sync()

def grub_args(command_line, marker):
    args = [x for x in command_line.split() if not x.startswith(('BOOT_IMAGE=', 'omni5_test=', 'hp_firmware_test='))]
    if not any(x.startswith('root=') for x in args): raise RepairError('Running kernel has no root= parameter.')
    if not all(re.fullmatch(r'[A-Za-z0-9_./=,:+@%-]+', x) for x in args):
        raise RepairError('Kernel command line contains unsupported GRUB syntax; manual review required.')
    if not re.fullmatch(r'[A-Za-z0-9-]+', marker): raise RepairError('Invalid boot marker.')
    return ' '.join(args + ['omni5_test='+marker])

def archive_file(extracted, name):
    """Resolve initrd symlinks inside the extracted tree, never against the host."""
    root = Path(extracted)/'main'
    if not root.is_dir(): root = Path(extracted)
    p = root/str(name).lstrip('/')
    for _ in range(40):
        if not p.is_symlink():
            resolved = p.resolve()
            if not resolved.is_relative_to(root.resolve()): raise RepairError('Initrd path escapes the extracted tree.')
            return resolved
        target = os.readlink(p)
        p = root/target.lstrip('/') if target.startswith('/') else p.parent/target
    raise RepairError('Initrd symlink loop.')
