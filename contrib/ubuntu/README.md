# Ubuntu integration work

These reports move the reference laptop's fixes into Ubuntu's normal hardware-enablement process:

- [Ubuntu Concept device tracker #2169090](https://bugs.launchpad.net/ubuntu-concept/+bug/2169090) covers the device tree, installer selection, Wi-Fi board data, audio, Fn keys and keyboard backlight.
- [qcom-firmware-extract bug #2169092](https://bugs.launchpad.net/ubuntu/+source/qcom-firmware-extract/+bug/2169092) contains an attached, applicable patch adding the `HP OmniBook 5` model mapping for Ubuntu's devel package.
- [alsa-ucm-conf bug #2169093](https://bugs.launchpad.net/ubuntu/+source/alsa-ucm-conf/+bug/2169093) requests the upstream OmniBook UCM match for Ubuntu 26.10.
- [Ubuntu kernel bug #2167217, comment 3](https://bugs.launchpad.net/ubuntu/+source/linux/+bug/2167217/comments/3) links the missing X1P42100 OmniBook 5 device tree to the 26.10 Snapdragon kernel work.

The patch in this directory was checked with `git apply --check` against Ubuntu's `ubuntu/devel` qcom-firmware-extract commit `eb0004e5dd3cd74c5cd62a1f19ac1e3b06f520bd` (package version 20). It addresses GPU/ADSP/CDSP extraction. It does not redistribute proprietary firmware or the Wi-Fi board descriptor.

The Markdown files preserve the submitted reports as reviewable source. Follow-up findings should go to the central device tracker first, then to the narrow package bug when a package owns the fix.
