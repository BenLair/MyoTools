# MyoTools

**MyoTools** is a suite of four complementary applications for quantitative skeletal muscle imaging. It provides interactive workflows for muscle-fiber segmentation, fiber typing, myonuclear fusion, and myotube surface measurement.

The current stable suite is **v0.4.1**. Pretrained model weights are distributed separately through [GitHub Releases](https://github.com/BenLair/MyoTools/releases); application packages are distributed only through the `Downloads/` folder of this repository.

## Download and install

| Operating system | Complete package | Installation |
| --- | --- | --- |
| Linux | [MyoTools-Linux.zip](Downloads/MyoTools-Linux.zip?raw=true) | Extract the ZIP, then run `bash INSTALL.sh` |
| Windows | [MyoTools-Windows.zip](Downloads/MyoTools-Windows.zip?raw=true) | Extract the ZIP, then run `INSTALL.bat` |

Each ZIP contains the Hub and all four applications, their configuration, and OS-specific installation scripts. Packages **do not contain** your data, conda environments, or pretrained weights. The first installation downloads the required software dependencies; subsequent software updates do not reinstall unchanged Conda environments.

Always download the ZIP corresponding to your system and extract it completely. Start the Hub using the desktop shortcut or `LAUNCH.sh` / `LAUNCH.bat`.

## Applications

| Application | Purpose | User guide |
| --- | --- | --- |
| **MyoSeg** | Segment muscle fibers from fluorescence or hematoxylin/eosin microscopy images; export cross-sectional area and Feret measurements | [How to use MyoSeg](MyoSeg/MyoSeg_How_to_Use.md) |
| **MyoClass** | Assign muscle-fiber types and quantify marker patterns using automatic, manual, and inferred marker modes | [How to use MyoClass](MyoClass/MyoClass_How_to_Use.md) |
| **MyoFuse** | Identify and classify nuclei and estimate myotube fusion index from in vitro microscopy | [How to use MyoFuse](MyoFuse/MyoFuse_How_to_Use.md) |
| **MyoSurface** | Calculate myotube coverage using corrected images, threshold previews, masks, and CSV exports | [How to use MyoSurface](MyoSurface/MyoSurface_How_to_Use.md) |

## Models

Select **Models** from the Hub to download the required pretrained weights. Downloaded files are checked against their published sizes and SHA-256 digests, and placed inside the local `Hub/runtime/models/` directory (where applicable). You may also select a custom model manually inside each application. MyoSurface does not require an external pretrained model.

Model downloads are separate from application downloads. Available model releases include [MyoSeg](https://github.com/BenLair/MyoTools/releases/tag/MyoSeg), [MyoSeg_HE](https://github.com/BenLair/MyoTools/releases/tag/MyoSeg_HE), [MyoClass](https://github.com/BenLair/MyoTools/releases/tag/MyoClass), and [MyoNuclei](https://github.com/BenLair/MyoTools/releases/tag/MyoNuclei). The MyoFuse Svetlana classifier is handled by its own installer.

## Updating and rollback

Select **Check for updates** from the Hub. Stable installations follow **only this public repository’s `main` branch**. They cannot download software updates from a private or experimental source. The updater verifies the published ZIP and distribution manifest before offering installation. Save your work and close running applications before confirming an update.

The updater preserves Conda environments, downloaded models, and scientific data. Changes to Conda environment specifications require a separate installation procedure and are rejected by the updater. A previous software version can be restored through the Hub’s rollback workflow when a valid backup is available.

Updates and rollback remain subject to platform and process-safety limitations. Preserve copies of valuable data and verify complex analyses before relying on a newer version.

## Integrity and requirements

[SHA256SUMS.txt](Downloads/SHA256SUMS.txt) lists the ZIP checksums. Every archive contains a `DISTRIBUTION.json` manifest with the suite version, stable update source, and per-file SHA-256 values.

A working Python/Conda setup or internet access to install Miniforge is required, along with adequate storage for PyTorch and related packages. A compatible NVIDIA GPU is optional; the applications can run on CPU.

## Uninstallation

Choose **Uninstall MyoTools** from the Hub or run the included `UNINSTALL.sh` / `UNINSTALL.bat`. The uninstaller removes only resources whose ownership it can verify. It preserves third-party Conda installations, pretrained models, images, outputs, and other scientific data.

## Contact and source

[GitHub repository](https://github.com/BenLair/MyoTools) · [Report an issue](https://github.com/BenLair/MyoTools/issues)

The source notebooks and runtime code for each version are bundled in the downloadable packages. See the four user guides above for workflows and output descriptions.
