# Contributing

Please distinguish **detected**, **software-verified** and **physically tested** results. This release was validated on one 16-bf reference laptop; reports from other units are useful even when installation is blocked.

Start with `./omni5 doctor --json` as your normal desktop user. Review the output before posting it. Include model family, kernel/version, desktop version, device-tree origin, Wi-Fi PCI subsystem/QMI chip/board IDs, relevant firmware error messages and the exact physical test. Do not upload serials, SSIDs, MAC/IP addresses, recovery keys, complete Windows driver packages or raw private logs.

For kernel/DTB/EC issues, contribute to the [upstream OmniBook 5 discussion](https://github.com/jglathe/linux_ms_dev_kit/discussions/56). For toolkit bugs, open an issue here with the command, error and a minimal redacted report. Credit the upstream work and avoid duplicate promotional posts across unrelated discussions.

To add a model, kernel or boot layout, preserve a known-working entry, validate the firmware paths and board tuple, inspect the candidate initrd, physically test the separate boot, confirm audio protection limits and demonstrate rollback. Add a meaningful safety test for any changed boundary. Do not simply broaden `validate_hardware()` or add a `--force` bypass.

Tests require only the Python standard library:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q omni5 omni5lib helpers
```

GNOME integration needs the distribution's `python3-gi`. Keep root operations in `repair.py`, desktop operations in `desktop.py`, and read-only checks/source selection in `core.py`. Never execute firmware, use shell-expanded input, recursively delete mountpoints or publish firmware blobs without verified redistribution rights.
