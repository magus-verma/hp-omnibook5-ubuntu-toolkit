# Reference repair: reproducible findings

The repair that motivated this project recovered a booting Ubuntu 26.04.1 ARM64 installation on HP OmniBook 5 Laptop 16-bf0xxx. The laptop used `7.2.2-jg-0-qcom-x1e` and `/boot/x1p42100-hp-omnibook-5.dtb`. Its original kernel, initrd and DTB were retained byte-for-byte. A separate firmware initrd was built, inspected and successfully booted before being made default.

## Problems identified

1. **Wi-Fi:** the stock WCN6855 board file lacked the HP subsystem/QMI tuple. `ath11k_pci` was correct; an earlier script had incorrectly blacklisted it and expected ath12k.
2. **GPU:** the HP DTB requested `qcdxkmsucpurwa.mbn`. An alias to a different stock firmware did not match that request; the matching local Windows HP driver supplied it.
3. **Audio/DSP:** exact HP ADSP/CDSP firmware and PD metadata were missing. `pd-mapper` failed with no maps, the DSPs did not start, and no sound card appeared.
4. **Topology:** the sound-card topology needed the top-level `qcom/x1e80100/<card>-tplg.bin` path, rather than only a nested laptop firmware path.
5. **Gain:** an older gain-5 workaround made the current setup extremely quiet. The actual current controls had a `WSA` prefix and a digital maximum of 81. An HP-specific UCM profile initialized those controls, and the generic codec profile was restored.
6. **Keyboard:** Fn did not change the F-row events. Brightness/media functions were provided through Super+F bindings; keyboard lighting had no exposed Linux control.

## Successful validation

- Internal Wi-Fi connected after reboot; an HTTPS request explicitly bound to it returned successfully.
- `glxinfo -B` reported **Adreno X1-45** and **Accelerated: yes**.
- Both remote processors reported **running**; `pd-mapper` was active.
- ALSA showed **X1P42100-HP-OMNIBOOK-5**; speakers and microphone endpoints appeared.
- The owner heard speaker playback, but reported insufficient loudness.
- Super+F3/F4/F6/F7/F8/F9/F10/F12 were confirmed by the owner.
- Original boot hashes remained unchanged and the fallback menu entry was preserved.

The original repair initrd included 12 required HP firmware/board/topology files with matching checksums. Its permanent future-build hook was later extended with stock GPU SQE/GMU microcode; the already boot-tested image was retained. The new reusable installer includes that microcode in its candidate checks.

The selected local Windows GPU driver reported `DriverVer=02/28/2026,31.0.148.0`; `qcdxkmsucpurwa.mbn` SHA-256 was:

```text
63d53b1908d2c053099680e4403b410a3f59f18ecd395586bb3d2ed33a86fea6
```

This is reference evidence, not a universal firmware pin. The toolkit chooses complete local driver sets by INF version and records their hashes. No Windows binaries are included in the repository.

## Changes not made

The repair did not flash BIOS/EC, repartition storage, write the Windows filesystem or replace the recovered kernel. An old force-start remoteproc service was disabled. Generic kernel installation and rebuilding every boot image were avoided after reviewing the previous boot failure.

Raw logs, full driver-store archives, disk/EFI backups, private recovery-chat contents, partition UUIDs, network identifiers and credentials remain local. This document and [commands.md](commands.md) capture the transferable steps without publishing those artifacts. Intermediate failed repair scripts are not offered as installers.

## Toolkit verification

The reusable toolkit passed 26 automated safety tests, Python compilation, live read-only hardware diagnosis and a no-write install plan on the reference laptop. A second complete installation using this new installer has not been performed. Firmware extraction/initrd building/reboot were validated during the underlying repair, using the earlier one-machine scripts.

Native Fn mode, keyboard lighting and satisfactory loudness remain open. Camera capture, Bluetooth pairing, microphone/headphones, external display and sleep/resume still need physical tests. See [hardware-status.md](hardware-status.md).
