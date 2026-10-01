"""Stage a firmware boot without replacing the recovered boot image."""
from contextlib import nullcontext
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from .core import (TESTED_KERNEL, FW_REL, FW_ROOT, STATE, DTB, BOARD_REL, TOPOLOGY_REL,
                   TOPOLOGY_SOURCE, GPU_MICROCODE, ENTRY, MENU, HOOK, HP_UCM, BOOT_ID, BOOT_TITLE,
                   RepairError, Transaction, run, sha, text, hardware, validate_hardware,
                   select_firmware, readonly_windows, obtain_board, grub_args, archive_file, hp_sound_card)

def require_root():
    if os.geteuid() != 0: raise RepairError('Use sudo for this system operation. Doctor and shortcuts run without sudo.')

def make_plan(h):
    validate_hardware(h)
    return {'operation': 'stage a separate firmware test boot', 'kernel_unchanged': TESTED_KERNEL,
            'firmware_target': str(FW_ROOT/FW_REL), 'wifi_target': str(FW_ROOT/BOARD_REL),
            'audio_profile': str(HP_UCM), 'boot_entry': BOOT_TITLE,
            'default_changed': False, 'automatic_reboot': False,
            'backups': str(STATE), 'unknowns': ['native Fn mode', 'keyboard backlight', 'maximum speaker loudness']}

def prerequisite_check(windows_device):
    commands = ['mkinitramfs', 'lsinitramfs', 'unmkinitramfs', 'grub-mkconfig', 'grub-script-check',
                'grub-probe', 'grub-editenv', 'findmnt', 'fdtget', 'amixer', 'alsaucm', 'zstd', 'modinfo', 'pd-mapper']
    if windows_device: commands += ['blkid', 'mount', 'umount', 'dislocker', 'ntfs-3g']
    missing = [c for c in commands if not shutil.which(c)]
    if missing: raise RepairError('Missing tools: '+', '.join(missing)+'. See docs/install.md for Ubuntu packages.')
    for p in [DTB, Path('/boot/vmlinuz-'+TESTED_KERNEL), Path('/boot/initrd.img-'+TESTED_KERNEL), TOPOLOGY_SOURCE]:
        if not p.is_file(): raise RepairError('Missing required file: '+str(p))
    unit = Path('/usr/lib/systemd/system/pd-mapper.service')
    if not unit.is_file() or 'ExecStart=/usr/bin/pd-mapper' not in unit.read_text():
        raise RepairError('The packaged PD mapper unit is missing or unrecognized; install protection-domain-mapper.')
    if 'masked' in run(['systemctl', 'show', 'pd-mapper', '-p', 'UnitFileState', '--value']).stdout:
        raise RepairError('PD mapper is deliberately masked. Review that policy before proceeding.')
    if os.stat('/boot').st_dev != os.stat('/').st_dev or run(['findmnt', '-n', '-o', 'FSTYPE', '-T', '/']).stdout.strip() != 'ext4':
        raise RepairError('This release requires /boot on the ext4 root filesystem. Separate /boot and Btrfs need a reviewed GRUB layout.')
    source = run(['findmnt', '-n', '-o', 'SOURCE', '-T', '/']).stdout.strip()
    if not re.fullmatch(r'/dev/nvme[0-9]+n[0-9]+p[0-9]+', source):
        raise RepairError('This release validates only a plain NVMe ext4 root partition. Encrypted/LVM roots need a reviewed GRUB layout.')
    model = run(['fdtget', '-t', 's', DTB, '/', 'model']).stdout.strip()
    live_model = Path('/sys/firmware/devicetree/base/model').read_bytes().rstrip(b'\0').decode()
    if model != live_model: raise RepairError('The saved boot DTB differs from the running device-tree model.')
    saved_dtb = DTB.read_bytes()
    for name in ['qcadsp8380.mbn', 'adsp_dtbs.elf', 'qccdsp8380.mbn', 'cdsp_dtbs.elf', 'qcdxkmsucpurwa.mbn']:
        if (str(FW_REL/name).encode()+b'\0') not in saved_dtb:
            raise RepairError('The saved DTB lacks the supported firmware path: '+name)
    for module in ['nvme', 'qcom_q6v5_pas', 'msm', 'ath11k_pci']:
        run(['modinfo', '-F', 'filename', module])

def audio_profile(tx):
    main = Path('/usr/share/alsa/ucm2/conf.d/x1e80100/x1e80100.conf').resolve()
    template = Path('/usr/share/alsa/ucm2/Qualcomm/x1e80100/LENOVO-T14s.conf')
    if not main.is_file() or not template.is_file(): raise RepairError('Current x1e80100 ALSA UCM files are missing; update alsa-ucm-conf.')
    hp = template.read_text()+'''
# HP OmniBook 5: actual prefixed controls, with the tested kernel's limits.
FixedBootSequence [
 cset "name='WSA WSA_RX0 Digital Volume' 81"
 cset "name='WSA WSA_RX1 Digital Volume' 81"
]
'''
    tx.write(HP_UCM, hp)
    content = main.read_text()
    include = 'True.Include.hpob5.File "/Qualcomm/x1e80100/HP-OmniBook5-Toolkit.conf"'
    if 'If.HPOmniBook5' in content:
        content, count = re.subn(r'True\.Include\.hpob5\.File\s+"[^"]+"', include, content)
        if count != 1: raise RepairError('Existing HP UCM override requires manual review.')
    else:
        block = '''If.HPOmniBook5 {
 Condition {
  Type RegexMatch
  String "${var:DMI_info}"
  Regex "HP.*Omni[Bb]ook.*5.*"
 }
 '''+include+'''
}

'''
        if 'If.LENOVOT14s' not in content: raise RepairError('Unrecognized x1e80100 UCM layout.')
        content = content.replace('If.LENOVOT14s', block+'If.LENOVOT14s', 1)
    tx.write(main, content)
    # Syntax/import validation. ALSA initialization is applied by the desktop session.
    if shutil.which('alsaucm') and '--- no soundcards ---' not in text('/proc/asound/cards'):
        run(['alsaucm', '-c', hp_sound_card(text('/proc/asound/cards')), 'list', '_verbs'])

def known_old_workarounds(tx):
    wifi = Path('/etc/modprobe.d/hp-omnibook5-wifi.conf')
    if wifi.is_file() and 'blacklist ath11k_pci' in wifi.read_text():
        tx.remove(wifi)
    audio = Path('/etc/modprobe.d/hp-omnibook5-audio.conf')
    if audio.is_file() and 'HP OmniBook 5 Audio module ordering' in audio.read_text():
        tx.remove(audio)
    # Any other active blacklist is left for explicit review, not silently overridden.
    for p in Path('/etc/modprobe.d').glob('*.conf'):
        if re.search(r'^\s*blacklist\s+ath11k(?:_pci)?\b', p.read_text(), re.M):
            raise RepairError(f'Wi-Fi is still blacklisted in {p}; review it before proceeding.')
    service = Path('/etc/systemd/system/qcom-remoteproc.service')
    if service.is_file() and 'echo start >' in service.read_text():
        # Remove only the known hand-written force-start service, with its enablement link.
        tx.preserve(service)
        link = Path('/etc/systemd/system/multi-user.target.wants/qcom-remoteproc.service')
        if link.is_symlink(): tx.remove(link)
        tx.remove(service)
        run(['systemctl', 'daemon-reload'])

def configure_pd_mapper(tx):
    unit = Path('/usr/lib/systemd/system/pd-mapper.service')
    link = Path('/etc/systemd/system/multi-user.target.wants/pd-mapper.service')
    if link.exists() or link.is_symlink():
        if not link.is_symlink() or link.resolve() != unit.resolve():
            raise RepairError('Existing PD mapper enablement differs from the packaged unit; review it first.')
    else:
        tx.symlink(str(unit), link)
        run(['systemctl', 'daemon-reload'])

def firmware_hook(required_names):
    result = '''#!/bin/sh
case "$1" in prereqs) exit 0;; esac
. /usr/share/initramfs-tools/hook-functions
'''
    for m in ['nvme', 'qcom_q6v5_pas', 'msm', 'ath11k_pci']:
        result += 'manual_add_modules '+m+' || exit 1\n'
    for name in required_names:
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', name): raise RepairError('Invalid firmware path.')
        result += "add_firmware '"+name+"' || exit 1\n"
    return result

def validate_initrd(image, required, work):
    listing = run(['lsinitramfs', image]).stdout
    (work/'initrd-contents.txt').write_text(listing)
    if 'init' not in listing.splitlines(): raise RepairError('Candidate initrd has no init.')
    for module in ['nvme', 'qcom_q6v5_pas', 'msm', 'ath11k_pci']:
        builtin = run(['modinfo', '-F', 'filename', module]).stdout.strip() == '(builtin)'
        if not builtin and not re.search(r'/'+module+r'\.ko(?:\.zst)?$', listing, re.M):
            raise RepairError('Candidate initrd missing '+module)
    extracted = work/'extracted'
    run(['unmkinitramfs', image, extracted])
    for name, expected in required.items():
        p = archive_file(extracted, name)
        if not p.is_file() or sha(p) != expected:
            raise RepairError('Candidate firmware checksum failed: '+name)

def validate_grub_config(original, generated, stanza):
    if stanza.strip() not in generated: raise RepairError('Candidate GRUB entry was not generated correctly.')
    entries = r'^(?:menuentry|submenu)\s+[^\n]+'
    old = re.findall(entries, original, re.M); new = re.findall(entries, generated, re.M)
    if new != old+[stanza.splitlines()[0]]:
        raise RepairError('The new GRUB entry is not strictly appended after all original choices; review the layout.')
    for block in re.findall(r'^(?:menuentry|submenu)\b.*?^}', original, re.M | re.S):
        if block not in generated: raise RepairError('An original boot stanza changed; review the candidate manually.')
    defaults = r'^\s*set default=[^\n]+'
    if re.findall(defaults, original, re.M) != re.findall(defaults, generated, re.M):
        raise RepairError('Generated GRUB default differs from the current default; refusing to change it during staging.')

def stage(args):
    h = hardware(); plan = make_plan(h)
    if args.dry_run:
        print(json.dumps(plan, indent=2)); return
    require_root(); prerequisite_check(args.windows_device)
    if ENTRY.exists(): raise RepairError('A toolkit boot entry already exists. Use verify/finalize, or rollback its recorded backup first.')
    if not args.windows_root and not args.windows_device:
        raise RepairError('Supply --windows-root or --windows-device. No partition is selected automatically.')
    critical = [Path('/boot/vmlinuz-'+TESTED_KERNEL), Path('/boot/initrd.img-'+TESTED_KERNEL), DTB]
    original_hashes = {str(p): sha(p) for p in critical}
    estimate = sum(p.stat().st_size for p in critical)+512*1024*1024
    if shutil.disk_usage('/var/lib').free < estimate or shutil.disk_usage('/boot').free < 256*1024*1024:
        raise RepairError('Insufficient free space for backups and a separate candidate initrd.')
    tx = Transaction(); candidate = Path('/boot/initrd.img-'+TESTED_KERNEL+'-omni5-'+tx.directory.name)
    try:
        for i, p in enumerate(critical): shutil.copy2(p, tx.directory/f'boot-original-{i}')
        shutil.copy2('/boot/grub/grub.cfg', tx.directory/'grub-original.cfg')
        source_context = readonly_windows(args.windows_device) if args.windows_device else nullcontext(Path(args.windows_root))
        with source_context as windows:
            source = select_firmware(windows)
            # Copy the narrowly selected files before closing the read-only mount.
            stage_dir = tx.directory/'staged'; stage_dir.mkdir()
            manifest = {}
            for name, x in source.items():
                local = stage_dir/name; shutil.copyfile(x['path'], local)
                manifest[name] = {'sha256': sha(local), 'driver_version': x['driver_version']}
        board = obtain_board(stage_dir, args.board_file)
        known_old_workarounds(tx)
        required = {}
        for name in manifest:
            target = FW_ROOT/FW_REL/name; tx.copy(stage_dir/name, target)
            required[str(target)] = manifest[name]['sha256']
        tx.copy(board, FW_ROOT/BOARD_REL); required[str(FW_ROOT/BOARD_REL)] = sha(board)
        # A regular copy keeps the early-boot topology independent of host symlink targets.
        tx.copy(TOPOLOGY_SOURCE, FW_ROOT/TOPOLOGY_REL)
        required[str(FW_ROOT/TOPOLOGY_REL)] = sha(TOPOLOGY_SOURCE)
        audio_profile(tx)
        configure_pd_mapper(tx)
        names = [str(Path(p).relative_to(FW_ROOT)) for p in required]+GPU_MICROCODE
        hook = firmware_hook(names); tx.write(HOOK, hook, 0o755)
        for name in GPU_MICROCODE:
            choices = [Path('/usr/lib/firmware')/(name+s) for s in ('', '.zst', '.xz')]
            p = next((x for x in choices if x.is_file()), None)
            if not p: raise RepairError('Stock GPU microcode missing: '+name)
            required[str(p)] = sha(p)
        with tempfile.TemporaryDirectory(prefix='build-', dir=tx.directory) as temp:
            work = Path(temp); config = work/'config'
            shutil.copytree('/etc/initramfs-tools', config, symlinks=True)
            image = work/'candidate.img'
            print('Building a separate initrd. The recovered image is retained.', flush=True)
            p = run(['mkinitramfs', '-d', config, '-o', image, TESTED_KERNEL], timeout=600)
            (tx.directory/'initrd-build.log').write_text(p.stdout+p.stderr)
            validate_initrd(image, required, work)
            tx.copy(image, candidate, 0o600)
        command_line = grub_args(text('/proc/cmdline'), tx.directory.name)
        root_uuid = run(['grub-probe', '-t', 'fs_uuid', '/']).stdout.strip()
        if not re.fullmatch(r'[0-9a-fA-F-]+', root_uuid): raise RepairError('Invalid root filesystem UUID from grub-probe.')
        stanza = f'''menuentry '{BOOT_TITLE}' --id {BOOT_ID} {{
 insmod gzio
 insmod part_gpt
 insmod ext2
 search --no-floppy --fs-uuid --set=root {root_uuid}
 linux /boot/vmlinuz-{TESTED_KERNEL} {command_line}
 initrd {candidate}
 devicetree {DTB}
}}
'''
        tx.write(ENTRY, "#!/bin/sh\ncat <<'OMNI5_GRUB'\n"+stanza+"OMNI5_GRUB\n", 0o755)
        # Appended entry avoids shifting the original numeric defaults.
        tx.write(MENU, '# Keep current default; show fallback choices.\nGRUB_TIMEOUT_STYLE=menu\nGRUB_TIMEOUT=15\n')
        generated = tx.directory/'grub-candidate.cfg'
        p = run(['grub-mkconfig', '-o', generated]); (tx.directory/'grub-build.log').write_text(p.stdout+p.stderr)
        run(['grub-script-check', generated])
        validate_grub_config((tx.directory/'grub-original.cfg').read_text(), generated.read_text(), stanza)
        for name, expected in original_hashes.items():
            if sha(name) != expected: raise RepairError('Recovered boot file changed unexpectedly.')
        tx.copy(generated, '/boot/grub/grub.cfg', 0o600)
        receipt = {'id': tx.directory.name, 'hardware': h, 'firmware': manifest, 'required_checksums': required,
                   'original_boot_checksums': original_hashes, 'candidate': str(candidate), 'candidate_sha256': sha(candidate),
                   'boot_id': BOOT_ID, 'default_changed': False, 'reboot_performed': False, 'state': 'staged'}
        (tx.directory/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
        tx.write(STATE/'latest', tx.directory.name+'\n', 0o600); os.sync()
        print('Firmware staged successfully. Backup ID: '+tx.directory.name)
        print('Save work, reboot, and manually select: '+BOOT_TITLE)
        print('Keep the previous working entry as the fallback. Then run ./omni5 verify from the desktop.')
    except BaseException:
        tx.rollback(); run(['systemctl', 'daemon-reload'], check=False)
        raise

def latest_receipt():
    require_root()
    identifier = text(STATE/'latest')
    if not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[a-f0-9]{6}', identifier): raise RepairError('No valid staged repair receipt.')
    directory = STATE/identifier
    return directory, json.loads((directory/'receipt.json').read_text())

def finalize(confirm_working):
    directory, r = latest_receipt()
    if r['state'] != 'staged': raise RepairError('This repair has already been finalized; use its recorded rollback IDs.')
    if not confirm_working: raise RepairError('Verify Wi-Fi, audio and graphics after the test boot, then use --confirm-working.')
    if 'omni5_test='+r['id'] not in text('/proc/cmdline').split(): raise RepairError('The staged firmware image has not booted.')
    card = hp_sound_card(text('/proc/asound/cards'))
    for line in run(['grub-editenv', '/boot/grub/grubenv', 'list']).stdout.splitlines():
        if line.startswith('next_entry=') and line.split('=', 1)[1]:
            raise RepairError('A one-time GRUB next_entry is pending. Clear or consume it before finalizing.')
    for p, expected in r['original_boot_checksums'].items():
        if sha(p) != expected: raise RepairError('Original boot file changed since staging.')
    if sha(r['candidate']) != r['candidate_sha256']: raise RepairError('Candidate initrd changed.')
    for p, expected in r['required_checksums'].items():
        if sha(p) != expected: raise RepairError('Installed firmware changed since staging: '+p)
    for name, limit in [('WSA WSA_RX0 Digital Volume', 81), ('WSA WSA_RX1 Digital Volume', 81), ('SpkrLeft PA Volume', 6), ('SpkrRight PA Volume', 6)]:
        out = run(['amixer', '-D'+card, 'cget', 'name='+name]).stdout
        if f'max={limit},' not in out: raise RepairError('Speaker protection limit is not active: '+name)
    tx = Transaction()
    try:
        tx.write(MENU, 'GRUB_DEFAULT="'+BOOT_ID+'"\nGRUB_TIMEOUT_STYLE=menu\nGRUB_TIMEOUT=10\n')
        generated = tx.directory/'grub-final.cfg'; run(['grub-mkconfig', '-o', generated]); run(['grub-script-check', generated])
        if 'set default="'+BOOT_ID+'"' not in generated.read_text(): raise RepairError('New default did not validate.')
        tx.copy(generated, '/boot/grub/grub.cfg', 0o600)
        r['state'] = 'finalized'; r['default_changed'] = True; r['finalize_backup'] = tx.directory.name
        tx.write(directory/'receipt.json', json.dumps(r, indent=2)+'\n', 0o600); os.sync()
    except BaseException:
        tx.rollback(); raise
    print('Verified firmware boot is now default. Original boot entries remain available.')
    print('Default-setting rollback ID: '+tx.directory.name)

def rollback(identifier):
    require_root()
    if not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[a-f0-9]{6}', identifier): raise RepairError('Invalid backup ID.')
    directory = STATE/identifier
    if not (directory/'changes.json').is_file(): raise RepairError('Backup manifest not found.')
    from .core import restore_transaction
    restore_transaction(directory); run(['systemctl', 'daemon-reload'], check=False)
    print('Restored recorded files. No reboot or kernel replacement performed.')
