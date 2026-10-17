# Contributing

Update_Most is a community-maintained, AI-assisted utility. Changes should be small, reviewable, and accompanied by appropriate tests.

## Core catalog submissions

Supply the developer's public repository, release tag or release-selection rule, the exact ZIP release asset, `core.json` ID, hardware target, install path and any additional dependencies. Identify the upstream author and license and distinguish hardware-tested releases from untested or experimental builds. Do not upload copyrighted games, BIOS images or firmware without explicit authorization.

## Changes to code

Describe what was changed, how it was tested, and any known limitations. Disclose when code, tests, or documentation were generated or modified with AI (including the tool used). Do not paste MiSTer GPL-3.0 updater code into this LGPL-2.1 repository. If third-party code is necessary, document licensing and attribution in `THIRD_PARTY_NOTICES.md` and ask for maintainers' review first.

Test before submitting a pull request:

```sh
python3 -m unittest discover -s tests -v
python3 update_most.py --list
```

Use synthetic test data. Do not commit BIOS bytes, game ROMs, personal SD-card contents, credentials or proprietary assets. Code should preserve existing saves, BIOS files and unrelated user content.