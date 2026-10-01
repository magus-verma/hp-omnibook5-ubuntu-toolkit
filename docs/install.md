# Install Ubuntu and prepare a supported boot

The goal is a bootable Ubuntu installation with a recoverable firmware repair. The toolkit takes over once Ubuntu boots with the supported kernel and explicit HP OmniBook 5 device tree. It does not automate disk partitioning or promise that an arbitrary Ubuntu ARM64 ISO supports this laptop.

## 1. Identify the laptop and preserve recovery options

This release accepts **HP OmniBook 5 Laptop 16-bf0xxx**, Snapdragon X Plus / X1P42100, Ubuntu **26.04 ARM64**, kernel **`7.2.2-jg-0-qcom-x1e`**, and a plain, unencrypted NVMe ext4 root with `/boot` on that same filesystem. The Wi-Fi subsystem and device-tree firmware paths must also match. Other layouts/models stop before system changes. The 14-he variant has related community work but is not automatically enabled here.

Keep a backup of your files, a bootable USB, your Windows recovery information and a preserved Windows installation or driver-store copy. The toolkit needs the HP Windows firmware files. In Windows, fully shut down before mounting its filesystem from Linux; a hibernated filesystem should remain untouched until Windows has shut down cleanly.

## 2. Use an image that supports Snapdragon and the exact laptop DTB

Start with the kernel maintainer's [extended Ubuntu 26.04 image installation instructions](https://github.com/jglathe/linux_ms_dev_kit/wiki/Installing-with-the-new%E2%80%90ish-Resolute-(26.04)-Ubuntu-extended-image) and the [OmniBook 5 hardware discussion](https://github.com/jglathe/linux_ms_dev_kit/discussions/56). Follow their current image/kernel instructions and verify any checksums they provide. Select the **OmniBook 5** device tree; the OmniBook X is a different model.

Write the image using your normal USB imaging tool and boot its explicit laptop entry. Choose your Ubuntu partition layout in the installer while preserving Windows. Keep USB Ethernet or phone tethering available for dependencies before the internal Wi-Fi is repaired.

Before the first installed-system reboot, complete the maintainer's post-install boot preparation. Preserve the exact DTB from the image at `/boot/x1p42100-hp-omnibook-5.dtb`, install the matched no-stubble kernel and module packages, and keep a GRUB entry with an explicit `devicetree` line. A generic boot entry without the appropriate DTB caused boot failure on the reference machine. The upstream guide explains preparation from the live environment; this toolkit does not run installation in an arbitrary `/target` chroot.

This release pins its repair logic to the kernel tested in the reference repair. If the maintainer now recommends another kernel, follow that recommendation for boot support and submit a validation report before adapting this toolkit. Do not downgrade a functioning newer setup just to pass this tool's checks.

## 3. Check the installed system

After successfully booting Ubuntu, inspect these read-only details:

```sh
uname -r
cat /sys/class/dmi/id/product_name
cat /proc/cmdline
ls -l /boot/vmlinuz-7.2.2-jg-0-qcom-x1e \
  /boot/initrd.img-7.2.2-jg-0-qcom-x1e \
  /boot/x1p42100-hp-omnibook-5.dtb
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
```

Keep this working entry. Do not run scripts that install generic kernels, rewrite every initrd or force Qualcomm remoteproc sysfs states. This toolkit stages an additional boot image instead.

## 4. Get the toolkit and dependencies

```sh
sudo apt install python3 python3-gi git zstd dislocker ntfs-3g initramfs-tools \
  grub-common kmod alsa-ucm-conf alsa-utils linux-firmware-qualcomm-misc \
  mesa-utils device-tree-compiler ibus protection-domain-mapper
git clone https://github.com/magus-verma/hp-omnibook5-ubuntu-toolkit.git
cd hp-omnibook5-ubuntu-toolkit
./omni5 doctor
./omni5 install --dry-run
```

The dry run performs hardware compatibility checks and prints the proposed scope. It does not mount Windows, download firmware, request root or write configuration. Dependency, free-space, DTB and boot-layout checks run before installation. Use `/usr/bin/python3` for any manual Python command; user-installed Python runtimes can lack the desktop GI bindings.

## 5. Stage the firmware boot

The easiest path is:

```sh
./omni5 setup
```

Select the Windows partition you identified with `lsblk`, or an already accessible Windows root directory. For a direct command:

```sh
sudo ./omni5 install --windows-device /dev/YOUR_WINDOWS_PARTITION
```

For NTFS, the partition is mounted `ro,norecover`. For BitLocker, the automatic path uses dislocker read-only clear-key mode followed by a read-only NTFS view. It never suspends BitLocker or changes Windows. If clear-key access is unavailable, it stops. Unlock interactively with your preferred tool in read-only mode and use:

```sh
sudo ./omni5 install --windows-root /mnt/YOUR_READ_ONLY_WINDOWS_ROOT
```

The directory must contain `Windows/System32/DriverStore/FileRepository`. Complete ADSP, CDSP and GPU sets are chosen by their INF `DriverVer`, validated, and copied before the temporary Windows mount closes. No complete Windows driver archive is copied. Root-only receipts record firmware hashes and versions.

Installation prints a backup ID. Keep it for rollback. It installs firmware overrides, an HP UCM profile, PD mapper enablement, a future initramfs hook and **one additional candidate initrd**. It checks that the recovered boot files are unchanged and the original top-level GRUB entries are retained. It leaves the previous default selected.

## 6. Test the additional boot

Save your work and reboot manually. Choose **HP OmniBook 5 - toolkit firmware boot** in the GRUB menu. If it fails, choose your old working entry on the next boot and use [recovery.md](recovery.md).

From the new desktop, without sudo:

```sh
./omni5 verify
glxinfo -B
cat /proc/asound/cards
cat /sys/class/remoteproc/remoteproc*/state
```

Connect to Wi-Fi and open an HTTPS page. Confirm `glxinfo -B` shows accelerated Adreno rendering instead of llvmpipe. Confirm the HP sound card is listed and the DSPs report `running`. Select the speakers in Settings and play a familiar audio clip at a comfortable level. Check microphone, camera, Bluetooth, headphones and sleep/resume yourself before relying on them; those are not fully validated by the reference repair.

If speakers remain quiet, see the documented gain limits in [hardware-status.md](hardware-status.md). The toolkit preserves protection limits and cannot promise Windows-equivalent loudness.

## 7. Add shortcuts and select the tested default

```sh
./omni5 shortcuts
```

Hold Windows/Super with the F-row keys shown in the [shortcut table](hardware-status.md#keyboard-shortcuts). This preserves ordinary F keys. GNOME 50 is the tested desktop. F5 keyboard lighting requires driver/EC work and is not emulated by this tool.

Only after the staged boot works and physical tests are satisfactory:

```sh
sudo ./omni5 finalize --confirm-working
```

Finalization checks the boot marker, unchanged original boot files, candidate checksum, HP sound card and current kernel speaker limits, then makes the tested entry the default. The old boot entries remain in a visible 10-second menu. It prints a second backup ID for reverting this default change.
