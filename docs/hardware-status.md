# Hardware status and limits

This records one reference laptop, tested on 1 October 2026. Detected devices and driver state are not substitutes for physical tests.

| Component | Status | Remaining work |
| --- | --- | --- |
| Model | HP OmniBook 5 Laptop 16-bf0xxx; board 8E33; Snapdragon X Plus X1P42100 | Additional model validation |
| OS/boot | Ubuntu 26.04 ARM64, recovered `7.2.2-jg-0-qcom-x1e`, explicit HP OmniBook 5 DTB | Validate newer kernels before widening the installer gate |
| Internal Wi-Fi | `ath11k_pci`, WCN6855 hw2.1; connected and HTTPS verified after reboot | Longer throughput/roaming tests |
| Graphics | Adreno X1-45; OpenGL hardware acceleration enabled | External-display and longer graphics tests |
| Audio | Both DSPs running; real HP sound card; speaker audio heard | Speaker loudness still unsatisfactory; microphone/headphones untested |
| Screen brightness | GNOME brightness changes worked; Super+F3/F4 confirmed | Native Fn behavior |
| Media shortcuts | Super+F6/F7/F8/F9/F10/F12 confirmed | See F1/F2 caveat below |
| Overview/emoji | Direct overview property helper tested; IBus picker available | Physical Super+F1/F2 confirmation pending |
| Keyboard light/Fn | No `kbd_backlight` endpoint; captured F-row events identical with and without Fn | Requires keyboard/EC or device-driver support |
| Bluetooth | Controller detected and powered | Pairing/audio test |
| Camera | HP True Vision FHD device detected | Image capture test |
| Battery | Capacity/charging state/temperature available | Runtime and charge-cycle tests |
| Storage | No NVMe/ext4 errors found in initial checks; package audit clean | No published SMART stress test |
| Suspend/resume | Not tested | Saved-work physical test |

The 14-he OmniBook 5 is discussed [upstream](https://github.com/jglathe/linux_ms_dev_kit/discussions/56), but this installer refuses it until the same boot, firmware and audio steps have been physically validated. It also refuses Intel/AMD OmniBook 5 machines, other Ubuntu releases, other kernels, different Wi-Fi chip/board IDs, separate `/boot` and Btrfs layouts. These are validation limits of this release, not statements that those configurations cannot run Linux.

## Speaker limits

The tested kernel caps the actual `WSA WSA_RX0/1 Digital Volume` controls at 81 (-3 dB) and each speaker PA control at 6 (0 dB). The HP UCM profile initializes the digital controls to 81. The reference laptop was still quiet in the owner's listening tests. A later 100% desktop-volume replay was performed within these caps and awaits a listening report.

Do not apply an old unprefixed gain-5 recipe to this kernel, remove the driver's caps, force amplifier registers, or raise desktop volume above 100% as an assumed fix. Consult the [Linux machine driver](https://github.com/torvalds/linux/blob/master/sound/soc/qcom/x1e80100.c) and [Ubuntu's protection rationale](https://lists.ubuntu.com/archives/kernel-team/2026-April/167246.html) when adapting the audio setup. This toolkit does not solve the remaining loudness problem.

## Keyboard shortcuts

Run `./omni5 shortcuts` from your GNOME desktop session. It adds the following bindings and records previous values. The direct mode is optional; the default preserves normal F-key behavior.

| Hold Windows/Super + | Action |
| --- | --- |
| F1 | Window overview, using GNOME's `OverviewActive` session-bus property |
| F2 | IBus emoji picker; copy the chosen emoji and paste it |
| F3 / F4 | Screen brightness down / up |
| F5 | No binding: no supported keyboard-light interface exists |
| F6 | Speaker mute |
| F7 / F8 | Volume down / up |
| F9 | Microphone mute |
| F10 | Play/pause |
| F12 | Screenshot interface |

GNOME 50 is the tested environment. Earlier desktops may lack the brightness/screenshot schema keys and will be rejected before changing shortcuts. Native `toggle-overview` and IBus emoji-hotkey settings did not respond on the reference laptop, so F1/F2 use direct custom actions. The overview helper was tested; the owner's physical F1/F2 result remains pending. Other desktops need their own shortcut integration.

## Other observations

Boot messages included an uncatalogued OLED panel with conservative timings and duplicate USB-C alternate-mode descriptors. No corresponding functional problem was confirmed in the reference repair. The toolkit does not change BIOS, panel timing or EC registers speculatively.
