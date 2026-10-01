# [X1P] Support HP OmniBook 5 Laptop 16-bf0xxx (8E33)

## Summary

Please add the Snapdragon X Plus HP OmniBook 5 Laptop 16-bf0xxx as a supported Ubuntu device. This is separate hardware from the 14-he0099nr described in bug 2130300.

An Ubuntu installation currently needs a community kernel, an explicit device tree, locally extracted HP firmware, a device-specific Wi-Fi board descriptor, and an ALSA UCM update. With those pieces installed, Wi-Fi, accelerated graphics and speaker playback work on the tested laptop. Native Fn handling, keyboard backlight control and normal speaker loudness still need kernel/audio work.

## Hardware

- Product: `HP OmniBook 5 Laptop 16-bf0xxx`
- Family: `103C_5335KV HP OmniBook 5`
- Board: `HP 8E33`
- Firmware: `F.07` (2026-04-16)
- SoC/device tree: Qualcomm X1P42100; model `HP OmniBook 5`
- Wi-Fi: Qualcomm WCN6855 `17cb:1103`, subsystem `103c:8d9a`, QMI chip 18 / board 255
- Sound card after firmware/device-tree setup: `X1P42100-HP-OMNIBOOK-5`
- DMI modalias: `dmi:bvnQualcommTechnologiesInc.,InsydeInc.:bvrF.07:bd04/16/2026:br15.7:efr54.35:svnHP:pnHPOmniBook5Laptop16-bf0xxx:pvrConfigID:rvnHP:rn8E33:rvr54.35:cvnHP:ct10:cvrChassisVersion:skuC40F2PA#ACJ:pfa103C_5335KVHPOmniBook5:`

## Tested Ubuntu state

- Ubuntu 26.04.1 LTS arm64
- Community kernel `7.2.2-jg-0-qcom-x1e`
- Device tree `x1p42100-hp-omnibook-5.dtb`
- `hwe-qcom-x1e-meta` installed
- `qcom-firmware-extract` 17 installed; Ubuntu devel version 20 inspected

The custom device tree has model `HP OmniBook 5` and compatible strings `hp,omnibook-5`, `lenovo,thinkpad-t14s`, `qcom,x1p42100`. Its compatibility fallback is a community workaround and should not be treated as the final upstream binding.

## Current behavior

1. Mainline Linux and the Ubuntu 26.10 Snapdragon sync do not contain an `x1p42100-hp-omnibook-5.dts`.
2. `qcom-firmware-extract` version 20 rejects device-tree model `HP OmniBook 5`, although its existing file list covers the GPU/ADSP/CDSP files this laptop needs.
3. The packaged WCN6855 board data does not contain the laptop tuple `bus=pci,vendor=17cb,device=1103,subsystem-vendor=103c,subsystem-device=8d9a,qmi-chip-id=18,qmi-board-id=255`.
4. The installed ALSA UCM profile does not select the working HP/T14s setup. Upstream alsa-ucm-conf PR 860 adds the needed HP OmniBook match.
5. The keyboard exposes no `kbd_backlight` LED and Fn does not alter the observed F-row input events. GNOME Super+F-key mappings are only a user-space workaround.
6. Speaker playback works, but remains much quieter than expected at the driver's safe exposed maxima (digital 81 and PA 6).

## Requested Ubuntu integration

1. Land the HP OmniBook 5 device tree and bindings upstream, then include/backport it in Ubuntu's Snapdragon kernel and installer device selection.
2. Apply the attached `qcom-firmware-extract` mapping for `HP OmniBook 5` to `x1p42100/hp/omnibook-5`, and ensure the extracted firmware is included in initramfs.
3. Provide the WCN6855 board descriptor through an acceptable redistributable firmware path, or document an extraction route if redistribution is not permitted.
4. Sync/backport alsa-ucm-conf PR 860 (or its final upstream equivalent) and validate topology/UCM naming on the exact hardware.
5. Diagnose the EC/input and keyboard-backlight interfaces, and the low speaker gain, in the upstream kernel/audio stacks.
6. Add the product/board identity to installer and hardware-enable­ment matching so a clean Ubuntu install selects the supported kernel and device tree automatically.

## Evidence and reproducer

- Reproducible repair toolkit and sanitized hardware findings: https://github.com/magus-verma/hp-omnibook5-ubuntu-toolkit
- Community kernel/device-tree discussion and this machine's report: https://github.com/jglathe/linux_ms_dev_kit/discussions/56#discussioncomment-18689467
- Upstream ALSA UCM change and this machine's report: https://github.com/alsa-project/alsa-ucm-conf/pull/860#issuecomment-5922679327
- Existing distinct 14-inch Ubuntu tracker: https://bugs.launchpad.net/ubuntu-concept/+bug/2130300
- Ubuntu 26.10 Snapdragon kernel sync: https://bugs.launchpad.net/ubuntu/+source/linux/+bug/2167217

## Validation limits

Wi-Fi association and routed HTTPS, accelerated graphics, both DSP remote processors and physical speaker playback were verified. The camera and Bluetooth controller enumerate, but camera capture and Bluetooth pairing were not physically tested. Microphone recording, headphones, suspend/resume and external displays have not yet been validated. This report therefore does not claim complete hardware support.
