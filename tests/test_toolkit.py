"""Exercise safety boundaries without root, hardware writes, network or GI."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from omni5lib import core, repair
from omni5lib.desktop import bindings

def supported():
    return {'model': 'HP OmniBook 5 Laptop 16-bf0xxx', 'architecture': 'aarch64',
            'kernel': core.TESTED_KERNEL, 'os': 'ubuntu', 'os_version': '26.04',
            'wifi_hardware': [{'vendor': '0x17cb', 'device': '0x1103',
                               'subsystem_vendor': '0x103c', 'subsystem_device': '0x8d9a'}],
            'wifi_board_ids': [(18, 255)],
            'dt_firmware_names': [str(core.FW_REL/n) for n in
                                 ['qcadsp8380.mbn', 'adsp_dtbs.elf', 'qccdsp8380.mbn', 'cdsp_dtbs.elf', 'qcdxkmsucpurwa.mbn']]}

class HardwareSafety(unittest.TestCase):
    def test_valid_hardware(self):
        core.validate_hardware(supported())

    def test_wrong_platforms_stop(self):
        for key, value in [('model', 'HP OmniBook 5 Laptop 14-he0xxx'), ('model', 'HP OmniBook X'),
                           ('architecture', 'x86_64'), ('kernel', '6.19.0-generic'),
                           ('os', 'debian'), ('os_version', '24.04'), ('wifi_hardware', []),
                           ('wifi_board_ids', [(18, 254)]), ('dt_firmware_names', [])]:
            h = supported(); h[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(core.RepairError):
                core.validate_hardware(h)

    def test_dry_run_never_requires_root_mounts_downloads_or_changes(self):
        with patch.object(repair, 'hardware', return_value=supported()), \
             patch.object(repair, 'require_root') as root, \
             patch.object(repair, 'readonly_windows') as mount, \
             patch.object(repair, 'obtain_board') as download, \
             patch.object(repair, 'Transaction') as mutation, redirect_stdout(io.StringIO()) as out:
            repair.stage(SimpleNamespace(dry_run=True))
            self.assertFalse(json.loads(out.getvalue())['default_changed'])
            for action in (root, mount, download, mutation): action.assert_not_called()

    def test_wrong_hardware_stops_before_root_or_writes(self):
        h = supported(); h['architecture'] = 'x86_64'
        with patch.object(repair, 'hardware', return_value=h), \
             patch.object(repair, 'require_root') as root, patch.object(repair, 'Transaction') as mutation:
            with self.assertRaises(core.RepairError): repair.stage(SimpleNamespace(dry_run=False))
            root.assert_not_called(); mutation.assert_not_called()

    def test_sound_card_index_is_detected(self):
        cards = ' 0 [HDMI]: unrelated\n 2 [X1P42100HPOmniBo]: X1P42100-HP-OMNIBOOK-5\n'
        self.assertEqual(core.hp_sound_card(cards), 'hw:2')
        with self.assertRaises(core.RepairError): core.hp_sound_card(' 0 [HDMI]: unrelated')

class FirmwareSelection(unittest.TestCase):
    def create_store(self, root):
        store = root/'Windows/System32/DriverStore/FileRepository'; store.mkdir(parents=True)
        for prefix, names in core.FIRMWARE_GROUPS.items():
            self.folder(store, prefix+'old', names, '01/01/2025,1.0.0')
            self.folder(store, prefix+'new', names, '02/28/2026,31.0.148.0')
        return store

    def folder(self, store, name, names, version):
        folder = store/name; folder.mkdir()
        (folder/'driver.inf').write_bytes(('DriverVer = '+version+'\n').encode('utf-16'))
        for name in names:
            (folder/name).write_bytes(json.dumps({'sr_domain': {'domain': 'adsp'}}).encode() if name.endswith('.jsn') else b'\x7fELFfixture')
        return folder

    def test_newest_complete_version_wins(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); store = self.create_store(root)
            prefix, names = next(iter(core.FIRMWARE_GROUPS.items()))
            incomplete = self.folder(store, prefix+'incomplete', names, '01/01/2027,99.0')
            (incomplete/names[0]).unlink()
            selected = core.select_firmware(root)
            self.assertEqual(len(selected), 10)
            self.assertTrue(all(x['path'].parent.name.endswith('new') for x in selected.values()))
            self.assertEqual(selected['qcdxkmsucpurwa.mbn']['driver_version'][:3], (2026, 2, 28))

    def test_bad_firmware_stops(self):
        for bad in ('qcadsp8380.mbn', 'adspr.jsn'):
            with self.subTest(file=bad), tempfile.TemporaryDirectory() as d:
                root = Path(d); store = self.create_store(root)
                folder = next(p for p in store.glob('qcsubsys*new'))
                (folder/bad).write_bytes(b'not firmware' if bad.endswith('.mbn') else b'{"sr_domain": []}')
                with self.assertRaises(core.RepairError): core.select_firmware(root)

    def test_missing_store_stops(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(core.RepairError): core.select_firmware(Path(d))

    def test_symlink_set_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); store = self.create_store(root)
            for folder in store.glob('qcdx*'):
                p = folder/'qcdxkmsucpurwa.mbn'; p.unlink(); p.symlink_to('/etc/passwd')
            with self.assertRaises(core.RepairError): core.select_firmware(root)

    def test_wrong_board_checksum_or_tuple_stops(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'board'; p.write_bytes(core.BOARD_ID)
            with self.assertRaises(core.RepairError): core.validate_board(p)
            with patch.object(core, 'sha', return_value=core.BOARD_SHA): core.validate_board(p)
            p.write_bytes(b'wrong tuple')
            with patch.object(core, 'sha', return_value=core.BOARD_SHA), self.assertRaises(core.RepairError): core.validate_board(p)

class RecoverableChanges(unittest.TestCase):
    def test_created_enablement_link_is_removed_on_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); unit = root/'unit'; unit.write_text('unit')
            link = root/'wants/unit'; tx = core.Transaction(root/'state')
            tx.symlink(str(unit), link)
            self.assertEqual(link.resolve(), unit)
            tx.rollback(); self.assertFalse(link.is_symlink())

    def test_rollback_restores_contents_modes_symlinks_and_absence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); original = root/'original'; original.write_text('before'); original.chmod(0o640)
            symlink = root/'link'; symlink.symlink_to('original')
            absent = root/'absent'; tx = core.Transaction(root/'state')
            tx.write(original, 'after'); tx.write(original, 'after again')
            tx.write(symlink, 'replacement'); tx.write(absent, 'created')
            self.assertEqual(len(tx.changes), 3)
            self.assertEqual(tx.directory.stat().st_mode & 0o777, 0o700)
            tx.rollback()
            self.assertEqual(original.read_text(), 'before'); self.assertEqual(original.stat().st_mode & 0o777, 0o640)
            self.assertTrue(symlink.is_symlink()); self.assertEqual(os.readlink(symlink), 'original')
            self.assertFalse(absent.exists())

    def test_remove_and_dangling_link_restore(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); p = root/'dangling'; p.symlink_to('missing')
            tx = core.Transaction(root/'state'); tx.remove(p); tx.rollback()
            self.assertTrue(p.is_symlink()); self.assertEqual(os.readlink(p), 'missing')

    def test_directory_replacement_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); tx = core.Transaction(root/'state')
            with self.assertRaises(core.RepairError): tx.write(root, 'bad')

class BootSafety(unittest.TestCase):
    def test_grub_appends_without_changing_choices_or_default(self):
        original = 'set default="0"\nmenuentry \'recovery\' {\n linux /boot/original root=x\n}\n'
        stanza = 'menuentry \'toolkit\' --id omni5 {\n linux /boot/test root=x\n}\n'
        repair.validate_grub_config(original, original+stanza, stanza)

    def test_grub_reordered_stanzas_or_default_changes_stop(self):
        original = 'set default="0"\nmenuentry \'recovery\' {\n linux /boot/original root=x\n}\n'
        stanza = 'menuentry \'toolkit\' --id omni5 {\n linux /boot/test root=x\n}\n'
        for generated in [stanza+original, (original+stanza).replace('default="0"', 'default="1"'),
                          (original+stanza).replace('/boot/original', '/boot/bad')]:
            with self.subTest(generated=generated), self.assertRaises(core.RepairError):
                repair.validate_grub_config(original, generated, stanza)

    def test_cmdline_preserved_and_marker_replaced(self):
        out = core.grub_args('BOOT_IMAGE=(hd0,gpt5)/vmlinuz root=UUID=abcd ro clk_ignore_unused cma=128M efi=noruntime hp_firmware_test=old omni5_test=old', '20261001-000000-abcdef')
        self.assertEqual(out, 'root=UUID=abcd ro clk_ignore_unused cma=128M efi=noruntime omni5_test=20261001-000000-abcdef')

    def test_grub_injection_and_missing_root_refused(self):
        for line in ['ro', 'root=UUID=x;reboot', 'root=$bad', 'root=x "quoted"', 'root=x `reboot`', 'root=x ${bad}']:
            with self.subTest(line=line), self.assertRaises(core.RepairError): core.grub_args(line, 'test')
        with self.assertRaises(core.RepairError): core.grub_args('root=x', "test';reboot")

    def test_initrd_absolute_symlink_resolves_inside_archive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); main = root/'main'; (main/'usr/lib/firmware').mkdir(parents=True)
            p = main/'usr/lib/firmware/a'; p.write_text('firmware')
            (main/'alias').symlink_to('/usr/lib/firmware/a')
            self.assertEqual(core.archive_file(root, '/alias'), p)

    def test_initrd_escape_and_loop_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'main').mkdir(); p = root/'main/a'
            p.symlink_to('../../outside')
            with self.assertRaises(core.RepairError): core.archive_file(root, 'a')
            p.unlink(); p.symlink_to('a')
            with self.assertRaises(core.RepairError): core.archive_file(root, 'a')

    def test_initrd_firmware_checksum_failure(self):
        with tempfile.TemporaryDirectory() as d:
            work = Path(d); (work/'extracted/main').mkdir(parents=True)
            (work/'extracted/main/firmware').write_text('wrong')
            def fake_run(args, **kwargs):
                value = 'init\n' if args[0] == 'lsinitramfs' else '(builtin)' if args[0] == 'modinfo' else ''
                return SimpleNamespace(stdout=value)
            with patch.object(repair, 'run', side_effect=fake_run), self.assertRaises(core.RepairError):
                repair.validate_initrd(work/'candidate.img', {'/firmware': 'bad'}, work)

    def test_finalize_requires_confirmed_test_boot(self):
        r = {'id': '20261001-000000-abcdef', 'state': 'staged'}
        with patch.object(repair, 'latest_receipt', return_value=(Path('/unused'), r)), patch.object(repair, 'Transaction') as mutation:
            with self.assertRaises(core.RepairError): repair.finalize(False)
            with patch.object(repair, 'text', return_value='root=x'), self.assertRaises(core.RepairError): repair.finalize(True)
            mutation.assert_not_called()

    def test_firmware_hook_is_checked_and_never_forces_remoteproc(self):
        hook = repair.firmware_hook(['qcom/a.mbn'])
        self.assertIn("add_firmware 'qcom/a.mbn' || exit 1", hook)
        self.assertNotIn('echo start', hook)
        with self.assertRaises(core.RepairError): repair.firmware_hook(["bad';reboot"])

class ReadOnlyWindows(unittest.TestCase):
    def test_bitlocker_mount_is_readonly_and_unmount_order_correct(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)/'mount'; base.mkdir(); calls = []
            def fake_run(args, **kwargs):
                calls.append([str(x) for x in args])
                return SimpleNamespace(stdout='BitLocker\n' if args[0] == 'blkid' else '', returncode=0)
            with patch.object(Path, 'is_block_device', return_value=True), \
                 patch.object(core.tempfile, 'mkdtemp', return_value=str(base)), patch.object(core, 'run', side_effect=fake_run):
                with core.readonly_windows('/dev/test-windows') as windows:
                    self.assertEqual(windows, base/'windows')
            self.assertIn('--readonly', calls[1]); self.assertIn('--clearkey', calls[1])
            self.assertIn('loop,ro,norecover', calls[2])
            self.assertEqual(calls[-2:], [['umount', str(base/'windows')], ['umount', str(base/'unlocked')]])
            self.assertFalse(base.exists())

    def test_unmount_failure_keeps_mountpoint_intact(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)/'mount'; base.mkdir()
            def fake_run(args, **kwargs):
                if args[0] == 'umount': raise core.RepairError('busy mount')
                return SimpleNamespace(stdout='ntfs\n' if args[0] == 'blkid' else '', returncode=0)
            with patch.object(Path, 'is_block_device', return_value=True), \
                 patch.object(core.tempfile, 'mkdtemp', return_value=str(base)), patch.object(core, 'run', side_effect=fake_run):
                with self.assertRaises(core.RepairError):
                    with core.readonly_windows('/dev/test-windows') as windows: (windows/'still-mounted').write_text('retained')
            self.assertTrue((base/'windows/still-mounted').is_file())

class DesktopMapping(unittest.TestCase):
    def test_preserve_regular_keys_and_leave_f5_unbound(self):
        super_keys = [x[2] for x in bindings('super')]
        self.assertTrue(all(x.startswith('<Super>') for x in super_keys))
        self.assertIn('<Super>F8', super_keys); self.assertNotIn('<Super>F5', super_keys)
        self.assertIn('F8', [x[2] for x in bindings('direct')])
        with self.assertRaises(core.RepairError): bindings('unknown')

if __name__ == '__main__': unittest.main()
