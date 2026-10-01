# Recovery and rollback

## If the candidate does not boot

Power off and start again. Use the visible GRUB menu and choose the **entry you used successfully before installing this toolkit**. The toolkit retains that entry and its original kernel, initrd and DTB. A generic Ubuntu entry may still lack the necessary device tree; choose the verified entry rather than assuming the newest kernel will work.

The first toolkit install leaves the default unchanged and shows the menu for 15 seconds. Finalization shows it for 10 seconds. Firmware overrides also exist on the real root, so preserving the old initrd is not a guarantee against every firmware-related failure. If neither entry starts, use a known bootable Snapdragon image with the correct laptop DTB.

## Restore toolkit changes from Ubuntu

Installation prints an ID such as `YYYYMMDD-HHMMSS-abcdef`. Root-only backups are under `/var/lib/omni5/`. List them and inspect the recorded changes:

```sh
sudo ls /var/lib/omni5
sudo cat /var/lib/omni5/YOUR_INSTALL_ID/changes.json
sudo cat /var/lib/omni5/YOUR_INSTALL_ID/receipt.json
```

If you have not finalized:

```sh
sudo ./omni5 rollback YOUR_INSTALL_ID
```

If you finalized, revert the **default change first**, then the installation:

```sh
sudo ./omni5 rollback YOUR_FINALIZE_ID
sudo ./omni5 rollback YOUR_INSTALL_ID
```

`finalize_backup` in the installation receipt gives the default-change ID. Rollback restores the previous GRUB configuration and each file/symlink recorded before modification, removes newly installed candidate/config files, and reloads systemd's configuration. It does not reboot or replace the kernel. Already loaded firmware remains in memory until the next boot; select the original entry afterwards.

Run rollback soon after a failed repair. It restores recorded files even if you subsequently edited them; compare those changes first. Keep backups until you have another recovery path. Failed/interrupted installation attempts retain their backup directory for diagnosis while automatically reverting recorded system changes.

## Restore desktop shortcuts

Run as the same desktop user, without sudo:

```sh
./omni5 restore-shortcuts
```

The shortcut backup is at `${XDG_STATE_HOME:-~/.local/state}/omni5/shortcuts.json`. Restoring puts back the settings captured before installation. It can also revert later edits to those same shortcut settings. Normal F keys are preserved by the default Windows/Super mode.

## Live USB recovery notes

The toolkit never changes the EFI partition or runs `grub-install`. A failed firmware boot usually needs selection of the original entry, not reinstalling the bootloader.

If Ubuntu's GRUB configuration itself needs restoration, identify and mount your Ubuntu root from the live USB. Check the backup manifests inside its `var/lib/omni5/` before copying anything. `boot-original-0`, `boot-original-1` and `boot-original-2` are emergency copies of the tested kernel, original initrd and DTB; `grub-original.cfg` is the pre-install GRUB configuration. Do not blindly extract files to a disk named in someone else's example. The [upstream installation guide](https://github.com/jglathe/linux_ms_dev_kit/wiki/Installing-with-the-new%E2%80%90ish-Resolute-(26.04)-Ubuntu-extended-image) documents explicit DTB boot preparation.

On the reference machine, recovery depended on the matched no-stubble JG kernel, correct HP DTB and original command-line arguments. Replacing these with a generic kernel or rebuilding every image was outside the firmware repair's scope and had previously caused trouble.

## Windows mount cleanup

The installer unmounts the NTFS view before the dislocker mount. If an unmount fails, it leaves the mountpoint intact and reports an error instead of recursively deleting it. Inspect `findmnt` for `/run/omni5-*` mounts, close anything using them, and unmount the Windows view followed by the unlocked view. Do not remove files while a mount is still active. No recovery keys or Windows files are saved in public reports.
