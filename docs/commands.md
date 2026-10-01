# Commands and firmware layout

These are the generalized commands behind the reference repair. The toolkit wraps them with checks and backups. Replace placeholders with values you have verified on your own laptop; do not copy machine-specific disk names or UUIDs from another person's logs.

## Read-only diagnosis

```sh
./omni5 doctor --json
uname -a
cat /sys/class/dmi/id/product_name
cat /proc/cmdline
lspci -nnk
rfkill list
nmcli device status
cat /proc/asound/cards
wpctl status
glxinfo -B
cat /sys/class/remoteproc/remoteproc*/state
systemctl --failed
systemctl status pd-mapper --no-pager
ls /sys/class/backlight /sys/class/leds
```

Some manual commands can show host/network information. Review their output before posting it. `doctor --json` excludes SSIDs, MAC/IP addresses, DMI serials and credentials; still review a report before sharing it.

## Firmware installed

Local Windows sets are selected under `Windows/System32/DriverStore/FileRepository`:

| Folder prefix | Files selected |
| --- | --- |
| `qcsubsys_ext_adsp8380.inf_arm64_` | `qcadsp8380.mbn`, `adsp_dtbs.elf`, `adspr.jsn`, `adsps.jsn`, `adspua.jsn`, `battmgr.jsn` |
| `qcnspmcdm_ext_cdsp8380.inf_arm64_` | `qccdsp8380.mbn`, `cdsp_dtbs.elf`, `cdspr.jsn` |
| `qcdx8380.inf_arm64_` | `qcdxkmsucpurwa.mbn` |

All ten files go into `/usr/lib/firmware/updates/qcom/x1p42100/hp/omnibook-5/`. MBN/ELF files must have the ELF header; PD metadata must have an `sr_domain` object. These checks detect obvious invalid files, not cryptographic authenticity of a Windows driver package. Use your laptop's trusted driver store, not downloaded random firmware.

The Wi-Fi board override is `/usr/lib/firmware/updates/ath11k/WCN6855/hw2.1/board-2.bin`. Its source is the [maintainer's attachment](https://github.com/user-attachments/files/25822586/board-2.bin.zst.txt) in the [OmniBook 5 discussion](https://github.com/jglathe/linux_ms_dev_kit/discussions/56). The uncompressed SHA-256 is:

```text
dd17d8aaccdc3e8a0a82d0fd6858934d7c87cfc10c2658cfbb570e604d692afc
```

The required tuple is:

```text
bus=pci,vendor=17cb,device=1103,subsystem-vendor=103c,subsystem-device=8d9a,qmi-chip-id=18,qmi-board-id=255
```

The downloaded descriptor must match both. A different PCI subsystem is rejected before installation. The driver is `ath11k_pci`, not `ath12k`. The descriptor is fetched from its original source rather than redistributed in this repository.

The installed topology override is `/usr/lib/firmware/updates/qcom/x1e80100/X1P42100-HP-OMNIBOOK-5-tplg.bin.zst`, copied from the packaged `X1E80100-Romulus-tplg.bin.zst`. A topology only inside the nested laptop DSP directory does not satisfy the [Qualcomm topology loader](https://github.com/torvalds/linux/blob/master/sound/soc/qcom/qdsp6/topology.c). The Ubuntu package providing the reference source is `linux-firmware-qualcomm-misc`.

The permanent initramfs hook also requests `qcom/gen71500_sqe.fw` and `qcom/gen71500_gmu.bin`. On the reference setup, the initial GPU microcode request occurred before the real root was available and retried successfully afterwards. Including it in future candidate images addresses that early lookup without replacing the already verified original image.

## Audio settings

The runtime ALSA UCM template is the installed `LENOVO-T14s.conf`, copied into an HP-specific profile. It is selected through the existing x1e80100 UCM configuration. The toolkit does not distribute that template or change the generic WSA init file.

The HP profile initializes **`WSA WSA_RX0 Digital Volume`** and **`WSA WSA_RX1 Digital Volume`** to **81**. These are the actual prefixed controls on the tested kernel. Read them using the HP card index shown by `/proc/asound/cards`:

```sh
amixer -Dhw:YOUR_HP_CARD_INDEX cget 'name=WSA WSA_RX0 Digital Volume'
amixer -Dhw:YOUR_HP_CARD_INDEX cget 'name=WSA WSA_RX1 Digital Volume'
amixer -Dhw:YOUR_HP_CARD_INDEX cget 'name=SpkrLeft PA Volume'
amixer -Dhw:YOUR_HP_CARD_INDEX cget 'name=SpkrRight PA Volume'
```

The digital maximum must be 81 (-3 dB) and each PA maximum 6 (0 dB), as verified on the running laptop. The [upstream machine driver](https://github.com/torvalds/linux/blob/master/sound/soc/qcom/x1e80100.c) and [Ubuntu kernel team's explanation](https://lists.ubuntu.com/archives/kernel-team/2026-April/167246.html) describe the caps. The old gain-5 recommendation produced very quiet output with these control names and this kernel. Do not remove the kernel's protection or boost beyond the documented limits.

Desktop services apply the UCM profile after reboot. The toolkit does not force playback or set your desktop volume to 100%. Use the regular volume slider after selecting the speakers. `wpctl get-volume @DEFAULT_AUDIO_SINK@` reads the desktop volume.

## Building and validating boot files

The installer uses `mkinitramfs -d PRIVATE_CONFIG -o PRIVATE_CANDIDATE KERNEL` to create only its candidate. It checks `lsinitramfs` for `init` and required drivers, unpacks with `unmkinitramfs`, and compares every required firmware file's SHA-256. It keeps the existing `/boot/initrd.img-KERNEL` unchanged.

The new GRUB entry uses the running kernel's root and boot arguments, explicit DTB and candidate initrd. Unsupported argument syntax is rejected. It is appended through `/etc/grub.d/99_omnibook5_toolkit`; a generated config is checked using `grub-script-check`, original top-level entries are checked for retention, and only then is `/boot/grub/grub.cfg` replaced atomically.

Generic `update-initramfs -u -k all`, package/kernel replacement, `grub-install` and direct remoteproc sysfs writes were deliberately excluded from this repair. They would alter more of the recovered boot path than the firmware repair needs.
