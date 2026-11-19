# MyoTools

**MyoTools** is a suite of four complementary applications for quantitative skeletal muscle imaging. It provides interactive workflows for muscle-fiber segmentation, fiber typing, myonuclear fusion, and myotube surface measurement.

The current stable suite is **v0.5.0**. Pretrained model weights are distributed separately through [GitHub Releases](https://github.com/BenLair/MyoTools/releases); application packages are distributed only through the `Downloads/` folder of this repository.

## Download and install

| Operating system | Complete package | Installation |
| --- | --- | --- |
| Linux | [MyoTools-Linux.zip](Downloads/MyoTools-Linux.zip?raw=true) | Extract the ZIP, then run `bash INSTALL.sh` |
| Windows | [MyoTools-Windows.zip](Downloads/MyoTools-Windows.zip?raw=true) | Extract the ZIP, then run `INSTALL.bat` |

Each ZIP contains the Hub and all four applications, their configuration, and OS-specific installation scripts. Packages **do not contain** your data, conda environments, or pretrained weights. The first installation downloads the required software dependencies; subsequent software updates do not reinstall unchanged Conda environments.

Always download the ZIP corresponding to your system and extract it completely. Start the Hub using the desktop shortcut or `LAUNCH.sh` / `LAUNCH.bat`.

## Closing MyoTools

Each installation runs one Hub. Opening the shortcut again reopens its existing Hub rather than starting another server. Choose **Quit MyoTools** in the Hub when finished. If applications launched from the Hub are still open, save your work and confirm before they close. Closing a browser tab alone leaves the Hub and its applications running.

## Applications

| Application | Purpose | User guide |
| --- | --- | --- |
| **MyoSeg** | Segment muscle fibers from fluorescence or hematoxylin/eosin microscopy images; export cross-sectional area and Feret measurements | [How to use MyoSeg](MyoSeg/MyoSeg_How_to_Use.md) |
| **MyoClass** | Assign muscle-fiber types and quantify marker patterns using automatic, manual, and inferred marker modes | [How to use MyoClass](MyoClass/MyoClass_How_to_Use.md) |
| **MyoFuse** | Identify and classify nuclei and estimate myotube fusion index from in vitro microscopy | [How to use MyoFuse](MyoFuse/MyoFuse_How_to_Use.md) |
| **MyoSurface** | Calculate myotube coverage using corrected images, threshold previews, masks, and CSV exports | [How to use MyoSurface](MyoSurface/MyoSurface_How_to_Use.md) |

## Current workflows

MyoSeg supports independent multi-folder queues, with a separate output directory and workbook for each input. MyoFuse supports independent multi-folder runs with preserved results from previous launches. Preview and one-image tests use the first input folder. See the guides for resume behavior.

## Models

Select **Models** from the Hub to download the required pretrained weights. Downloaded files are checked against their published sizes and SHA-256 digests, and placed inside the local `Hub/runtime/models/` directory (where applicable). You may also select a custom model manually inside each application. MyoSurface does not require an external pretrained model.

Model downloads are separate from application downloads. Available model releases include [MyoSeg](https://github.com/BenLair/MyoTools/releases/tag/MyoSeg-v1.0.0), [MyoSeg_HE](https://github.com/BenLair/MyoTools/releases/tag/MyoSeg_HE-v1.0.0), [MyoClass](https://github.com/BenLair/MyoTools/releases/tag/MyoClass-v1.0.0), and [MyoNuclei](https://github.com/BenLair/MyoTools/releases/tag/MyoNuclei-v1.0.0). The MyoFuse Svetlana classifier is handled by its own installer.

## Updating and rollback

Select **Check for updates** from the Hub. Stable installations follow **only this public repository’s `main` branch**. They cannot download software updates from a private or experimental source. The updater verifies the published ZIP and distribution manifest before offering installation. Save your work and close running applications before confirming an update.

The updater preserves Conda environments, downloaded models, and scientific data. Changes to Conda environment specifications require a separate installation procedure and are rejected by the updater. A previous software version can be restored through the Hub’s rollback workflow when a valid backup is available.

Updates and rollback remain subject to platform and process-safety limitations. Preserve copies of valuable data and verify complex analyses before relying on a newer version.

## Updater maintenance correction

Suite **0.4.9**, maintenance build **1**, fixes false active-Hub reports caused by recycled process IDs and improves maintenance status reporting. Application algorithms and dependency specifications are unchanged. A live process with an unknown creation time remains protected.

The original 0.4.9 updater cannot discover a correction with the same suite version. If your updater is blocked, close the Hub and all analysis windows. Download [repair_update.py](repair_update.py) from this repository and run it with Python against your existing extracted installation:

```bash
python3 /path/to/repair_update.py --root /mnt/ssd/MyoTools-Linux
```

On Windows, use `python` and your installation path. The helper verifies the archive and manifest from the official update origin, stages the verified updater temporarily, and asks you to type `UPDATE MYOTOOLS`. Reopen the Hub after it finishes. It preserves the usual checks for active Hubs, locally modified files and interrupted transactions, plus rollback backups. Do not delete PID markers or overwrite managed files manually. If the helper reports an error, retain its full output and the logs in `Hub/runtime/updates/`.

## Integrity and requirements

[SHA256SUMS.txt](Downloads/SHA256SUMS.txt) lists the ZIP checksums. Every archive contains a `DISTRIBUTION.json` manifest with the suite version, stable update source, and per-file SHA-256 values.

A working Python/Conda setup or internet access to install Miniforge is required, along with adequate storage for PyTorch and related packages. A compatible NVIDIA GPU is optional; the applications can run on CPU.

## Uninstallation

Choose **Uninstall MyoTools** from the Hub or run the included `UNINSTALL.sh` / `UNINSTALL.bat`. The uninstaller removes only resources whose ownership it can verify. It preserves third-party Conda installations, pretrained models, images, outputs, and other scientific data.

## Contact and source

[GitHub repository](https://github.com/BenLair/MyoTools) · [Report an issue](https://github.com/BenLair/MyoTools/issues)

The source notebooks and runtime code for each version are bundled in the downloadable packages. See the four user guides above for workflows and output descriptions.

## Included versions

| Application | Version |
| --- | --- |
| MyoSeg | 1.2.0 |
| MyoClass | 1.0.3 |
| MyoFuse | 1.1.3 |
| MyoSurface | 1.0.0 |

Multi-folder orchestration and exports are covered by synthetic tests. Cellpose inference, GPU memory behavior and interactive operation must be checked on representative images and the target operating system. The optional MyoFuse GPU + CPU reconstruction mode remains experimental.
