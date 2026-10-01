# alsa-ucm-conf: enable HP OmniBook 5 Snapdragon speaker profile

The Snapdragon X Plus HP OmniBook 5 Laptop 16-bf0xxx (`HP 8E33`) reaches a working sound card only after its device tree and ADSP/CDSP firmware are present. Its card is `X1P42100-HP-OMNIBOOK-5`, but Ubuntu's current UCM data does not select the working HP/T14s configuration.

Upstream alsa-ucm-conf PR 860 expands the HP match to OmniBook devices:

https://github.com/alsa-project/alsa-ucm-conf/pull/860

On this laptop, the equivalent UCM selection produces audible left/right speaker playback and both DSP remote processors remain running. This is hardware evidence for the match, but it is not a `Tested-by` for the exact PR commit because the installed files were repaired before that commit was checked out verbatim.

Please sync or backport the final upstream fix into Ubuntu 26.10 and validate it with the HP OmniBook 5 device tracker. Speaker output is still unusually quiet at the safe limits exposed by the present driver (digital 81, PA 6), so gain/topology work may remain after profile selection.

Hardware report: https://github.com/alsa-project/alsa-ucm-conf/pull/860#issuecomment-5922679327

Reproducer and sanitized evidence: https://github.com/magus-verma/hp-omnibook5-ubuntu-toolkit
