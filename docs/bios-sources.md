# BIOS source and rights review (development inventory)

This inventory records *what the catalog references*, not a legal determination or
permission to obtain any individual proprietary firmware image. Update_Most is
GPL-3.0-only. The [BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer)
**database** is published under MIT by ajgowans; that license cannot be
assumed to apply to the individual third-party ROM images it links. MiSTer
Update All and Downloader are GPL-3.0 and have not been copied.

The current development build automatically consults BiosDB references for
missing matching BIOS files, following the curator's current preference.
The user can disable these with `--no-mister-bios`. The rights/default
policy is still being reviewed in [issue #2](https://github.com/czarroland/update_most/issues/2).

| BIOS | Destination | Source index path or input | Size | Firmware permission |
|---|---|---|---:|---|
| Game Boy DMG original boot ROM (optional) | `system/gameboy.bios-dmg.bin` | `user-supplied` | 256 B | not established |
| Game Boy Color original boot ROM (optional) | `system/gameboy.bios-cgb.bin` | `games/GAMEBOY/boot1.rom` | 2304 B | not established |
| Game Boy Advance original boot ROM (optional) | `system/gba.bios.bin` | `games/GBA/boot.rom` | 16384 B | not established |
| ColecoVision OS-7 BIOS | `cores/alanswx.ColecoVision/coleco.rom` | Archive.org MAME 0.209 `coleco.zip` (`313 10031-4005 73108a.u2`) | 8192 B | not established |
| Apple IIgs ROM 01 | `cores/alanswx.AppleIIgs/rom01.rom` | `games/Apple-IIgs/boot1.rom` | 131072 B | not established |
| Apple IIgs ROM 3 | `cores/alanswx.AppleIIgs/rom3.rom` | `games/Apple-IIgs/boot.rom` | 262144 B | not established |
| Macintosh LC ROM | `cores/danifunker.MacLC/MacLC.rom` | Archive.org MAME 0.209 `maclc.zip` (`350eacf0.rom`) | 524288 B | not established |
| Bally Midway MCR SSIO timing PROM | `cores/alanswx.MCR/ssio.prom` | Archive.org MAME 0.209 `midssio.zip` (`82s123.12d`) | 32 B | not established |
| Neo Geo Pocket Color BIOS | `cores/Kitrinx.NGPC/boot0.rom` | `games/NGPC/boot0.rom` | 65536 B | not established |
| Neo Geo Pocket monochrome BIOS | `cores/Kitrinx.NGPC/boot1.rom` | `games/NGPC/boot1.rom` | 65536 B | not established |
| Tiger Game.com external BIOS | `cores/Kitrinx.GameCom/boot.rom` | `games/GameCom/boot.rom` | 262144 B | not established |

No executable or BIOS bytes from these sources are vendored in this repository.
Source URLs, catalog checksums, and file sizes are *identifiers and integrity
information*, not copyright grants. ColecoVision, Macintosh LC, and MCR SSIO
files are fetched only when missing, and both their source ZIP and extracted
bytes must match pinned SHA-256 values. A matching local file can be supplied
instead. The MCR PROM's mandatory 32-byte slot is verified against installed
Game Bub core metadata.

Release review requires confirming any needed authorizations for the specific
downloaded images and user-facing behavior. This document is source attribution,
not legal advice. Developed with **OpenAI ChatGPT** assistance.
