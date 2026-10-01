# HP OmniBook 5 Ubuntu Toolkit

A guided firmware repair and installation companion for the **Snapdragon X Plus HP OmniBook 5**. Built from a successfully recovered and reboot-tested Ubuntu setup, with an emphasis on keeping a working boot path.

**Initial release: tested on HP OmniBook 5 Laptop 16-bf0xxx, Ubuntu 26.04 ARM64, kernel `7.2.2-jg-0-qcom-x1e`, and the explicit OmniBook 5 DTB.** Hardware changes are deliberately blocked on other models, kernels, operating systems and boot layouts (encrypted/LVM roots, separate `/boot` and Btrfs are not validated). The 14-he variant is a future validation target; Intel/AMD OmniBooks and the OmniBook X are outside this release.

This is a firmware and configuration toolkit plus an Ubuntu installation guide. Native Fn mode, keyboard lighting and Windows-equivalent speaker loudness remain unresolved. It does not claim complete hardware support.

## Start here

If Ubuntu is not installed, follow [the installation guide](docs/install.md) first. If your matching Ubuntu setup already boots and needs these firmware fixes, install the dependencies and run the guided setup. A laptop already repaired with the earlier one-machine scripts does not need this installer rerun:

```sh
sudo apt install python3 python3-gi git zstd dislocker ntfs-3g initramfs-tools \
  grub-common kmod alsa-ucm-conf alsa-utils linux-firmware-qualcomm-misc \
  mesa-utils device-tree-compiler ibus protection-domain-mapper
git clone https://github.com/magus-verma/hp-omnibook5-ubuntu-toolkit.git
cd hp-omnibook5-ubuntu-toolkit
./omni5 doctor
./omni5 install --dry-run
./omni5 setup
```

The wizard asks which Windows partition or Windows root contains this laptop's drivers. It requests sudo only for system installation. No partition is selected automatically. It downloads the checksum-pinned Wi-Fi board descriptor and obtains GPU/DSP firmware from your own local Windows drivers.

Installation **stages** a separate boot image and shows the GRUB menu while keeping the previous default. Save work, reboot manually and select **HP OmniBook 5 - toolkit firmware boot**. After confirming Wi-Fi, graphics and physical speaker playback:

```sh
./omni5 verify
./omni5 shortcuts
sudo ./omni5 finalize --confirm-working
```

The final command makes the tested image the default. Your original kernel, initrd, DTB and boot entries remain available. `doctor`/`verify` currently report software state; a zero exit status means the hardware matches this release, **not** that every device passed a physical test.

## What is included

| Area | Toolkit action | Evidence on the reference laptop |
| --- | --- | --- |
| Wi-Fi | Correct `ath11k_pci` WCN6855 hw2.1 board descriptor for `17cb:1103 / 103c:8d9a`, chip 18, board 255 | Connected; HTTPS bound to the Wi-Fi interface succeeded |
| GPU | Exact `qcdxkmsucpurwa.mbn` requested by the OmniBook 5 device tree; stock Adreno microcode included in future initrds | Adreno X1-45, hardware acceleration enabled |
| Audio/DSP | ADSP/CDSP binaries, DTBs, PD metadata and correctly located topology; HP-specific ALSA UCM profile | Both DSPs running; real sound card present; speaker playback heard |
| Speaker gain | Actual prefixed digital controls initialized to 81; current kernel's digital/PA limits retained | The obsolete gain-5 workaround was corrected; loudness still needs work |
| Brightness/media keys | Reversible GNOME Windows/Super + F-row bindings | F3/F4/F6/F7/F8/F9/F10/F12 physically confirmed |
| Overview/emoji | Direct GNOME overview action and IBus emoji picker | Overview helper tested; physical F1/F2 confirmation pending |
| Boot protection | Separate candidate initrd, checksums, required modules, GRUB validation, original boot hashes, explicit test/finalize steps | Underlying firmware repair booted successfully with original boot files retained |

Camera and Bluetooth devices were detected; capture/pairing were not tested. Microphone recording, headphones, sleep/resume and external display are also untested. The reusable installer is new: its logic is covered by automated tests and read-only checks, but it has **not** been run through a second full hardware installation.

## Commands

```sh
./omni5 --help
./omni5 doctor --json                  # shareable report without SSIDs/MACs/serials
./omni5 install --dry-run              # compatibility and change plan only
./omni5 setup                         # guided setup, as your normal user
sudo ./omni5 install --windows-device /dev/YOUR_WINDOWS_PARTITION
sudo ./omni5 install --windows-root /mnt/YOUR_READ_ONLY_WINDOWS_ROOT
./omni5 shortcuts                     # Windows/Super + F keys; preserve regular F keys
./omni5 shortcuts --mode direct       # optional: ordinary F keys become media keys
./omni5 restore-shortcuts
./omni5 verify
sudo ./omni5 finalize --confirm-working
sudo ./omni5 rollback YOUR_BACKUP_ID
```

Replace the device/path placeholders after inspecting your own disk layout. For offline use, pass `--board-file /path/to/board-2.bin`; the exact checksum and hardware tuple are still checked. BitLocker support automatically uses **read-only clear-key access only**. For other BitLocker states, unlock interactively and supply a read-only mounted Windows root; the toolkit does not collect recovery keys.

## Protection and recovery

- Firmware goes into `/usr/lib/firmware/updates/`, preserving packaged originals.
- The packaged PD mapper is enabled for the next boot, with prior enablement backed up.
- Every changed system file has a root-only backup and an explicit rollback ID under `/var/lib/omni5/`.
- The recovered kernel/initrd/DTB are copied to the backup and checked for unexpected changes.
- The candidate initrd must contain its required modules and checksum-matching firmware before it is offered for boot.
- The first installation keeps the default boot selection. Only `finalize --confirm-working` changes it after a successful test boot.
- The toolkit does not partition disks, write Windows, flash BIOS/EC, upgrade kernels, force remote processors to start or reboot automatically.

If a test boot fails, select your **previous working entry** from GRUB. See [recovery and rollback](docs/recovery.md) for the commands and the reverse order required after finalization. File rollback can revert later edits to the same files; review the backup before using it on a system that has subsequently changed.

## Documentation

- [Ubuntu installation and first boot](docs/install.md)
- [Commands and firmware layout](docs/commands.md)
- [Recovery and rollback](docs/recovery.md)
- [Tested hardware and unresolved issues](docs/hardware-status.md)
- [Reference repair findings](docs/reference-repair.md)
- [Contributing and validating additional models](CONTRIBUTING.md)

## Tests

```sh
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 -m compileall -q omni5 omni5lib helpers
```

Tests exercise unsupported hardware rejection, no-write dry runs, firmware version selection, invalid board/firmware rejection, read-only Windows access and unmount failure handling, file/symlink rollback, GRUB argument restrictions, initrd checksum checks and test-boot confirmation. They do not pretend to emulate the laptop's drivers.

## Credits and licensing

The underlying kernel/DTB and board work comes from [Jens Glathe and the OmniBook 5 discussion contributors](https://github.com/jglathe/linux_ms_dev_kit/discussions/56), alongside Ubuntu, Linux, Mesa and ALSA contributors. This toolkit packages the steps observed on one laptop; it does not claim authorship of those drivers or firmware.

Toolkit code is MIT licensed. Proprietary Windows firmware, complete driver packages, kernel packages, disk images, personal logs and credentials are **not** included. Firmware remains subject to its original license; obtaining it from your local installation does not grant redistribution rights. See [the command reference](docs/commands.md) for source links and the board checksum.
