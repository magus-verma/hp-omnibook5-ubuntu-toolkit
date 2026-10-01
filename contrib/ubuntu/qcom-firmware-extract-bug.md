# qcom-firmware-extract: add HP OmniBook 5 (X1P42100) mapping

Ubuntu devel `qcom-firmware-extract` version 20 rejects the device-tree model `HP OmniBook 5`. The HP OmniBook 5 Laptop 16-bf0xxx uses X1P42100 and the destination expected by its device tree is:

`/usr/lib/firmware/updates/qcom/x1p42100/hp/omnibook-5`

The existing version 20 extraction list already includes the required GPU, ADSP and CDSP files, including `qcdxkmsucpurwa.mbn`. Only the model mapping is missing. The attached one-hunk patch adds:

```sh
"HP OmniBook 5")
    device_path="x1p42100/hp/omnibook-5"
    ;;
```

The mapping was checked against `/proc/device-tree/model` on the physical laptop and against the firmware path used by the working device tree. A complete device tracker and hardware evidence are in the linked Ubuntu Concept bug. The Wi-Fi `board-2.bin` is a separate packaging/licensing issue and is not included in this patch.

Source inspected: `ubuntu/devel` commit `eb0004e5dd3cd74c5cd62a1f19ac1e3b06f520bd` (version 20).

Public reproducer and patch: https://github.com/magus-verma/hp-omnibook5-ubuntu-toolkit/tree/main/contrib/ubuntu
