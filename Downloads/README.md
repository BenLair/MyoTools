# MyoTools stable installers

The **Linux** and **Windows** archives below are complete standalone MyoTools distributions. GitHub Releases are reserved for validated pretrained model weights, not software packages.

| System | Archive | Extracted folder | Installation |
| --- | --- | --- | --- |
| Linux | [MyoTools-Linux.zip](MyoTools-Linux.zip?raw=true) | [MyoTools-Linux/](MyoTools-Linux/) | Extract and run `bash INSTALL.sh` |
| Windows | [MyoTools-Windows.zip](MyoTools-Windows.zip?raw=true) | [MyoTools-Windows/](MyoTools-Windows/) | Extract and run `INSTALL.bat` |

Verify your download using [SHA256SUMS.txt](SHA256SUMS.txt). The `DISTRIBUTION.json` manifest in each archive records the version, platform, fixed public update source, and checksums of all packaged files.

Once installed, open the Hub via its desktop shortcut. The **Check for updates** page retrieves subsequent stable versions exclusively from `BenLair/MyoTools` on `main`, verifies the archive, and handles installation after explicit confirmation.

The four application user guides are also included in each ZIP. Conda environments, experimental code, and trained model weights are not embedded in the archive.
