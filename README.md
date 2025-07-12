# Offline Audio Book Player

A lightweight PyQt5 application for listening to audio books entirely offline. The player relies on VLC for playback and stores progress under `~/.config/m4bplayer` (or `%USERPROFILE%\.config\m4bplayer` on Windows).

## Features

- Resume playback from your last position for every book
- Built-in "Bookshelf" listing previously opened files
- Chapter list when `ffprobe` is available
- Switch between audio tracks if the media provides multiple streams
- Displays metadata and cover art
- Small settings dialog to adjust font sizes and clear stored data
- Bookmark dialog to save and load timestamps with notes
- Compact mode keeps a small window visible when minimized
- Slider adjusts to long books and shows a "Continue From" label
- Automatically reopens the last book when the program starts
- Optional real-time audio visualizer driven by ffmpeg with CPU/RAM stats (requires `pyqtgraph`, `numpy`, `pyaudio` and `ffmpeg`; stats shown when `psutil` is installed)

## Requirements

- Python 3.7 or newer
- [VLC](https://www.videolan.org/) so the `libvlc` libraries are discoverable
- [`ffprobe`](https://ffmpeg.org/ffprobe.html) for reading chapter information
- [`ffmpeg`](https://ffmpeg.org/) for the visualizer feature
- [`psutil`](https://pypi.org/project/psutil/) *(optional, for usage stats)*
- `pyqtgraph`, `numpy`, `pyaudio` *(optional, for real-time visualizer)*
- Python packages: `mutagen`, `python-vlc`, `PyQt5`, `pyttsx3`

Install the Python dependencies with:

```bash
pip install mutagen python-vlc PyQt5 pyttsx3 psutil pyqtgraph numpy pyaudio  # optional: psutil and visualizer libs
```

## Windows 11 Setup

1. Install [Python 3](https://www.python.org/downloads/windows/) and enable the *Add Python to PATH* option.
2. Install [VLC](https://www.videolan.org/) for Windows.
3. Download a static build of [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) and extract `ffprobe.exe` and `ffmpeg.exe` somewhere on your `PATH` (or point the application to them when prompted).
4. Open **PowerShell** or **Command Prompt** and run:

```powershell
pip install mutagen python-vlc PyQt5 pyttsx3 psutil pyqtgraph numpy pyaudio  # optional: psutil and visualizer libs
```

Run the application from the same terminal with:

```powershell
python m4b_playerV8.py
```

The configuration file will be created under `%USERPROFILE%\.config\m4bplayer\resume.dat`.

## Usage

Run the application with Python:

```bash
python m4b_playerV8.py
```

On first start, the player creates `~/.config/m4bplayer/resume.dat` to store progress, bookshelf entries and UI preferences. If VLC, ffprobe or ffmpeg cannot be located automatically, you will be prompted to select their locations.

Click **Visualizer** in the toolbar to open the optional real-time visualizer window. The widget decodes the audio with ffmpeg so the patterns react live to the book. Use the drop-down to choose **Wave**, **Bars** or **Circle**. CPU and RAM usage are displayed when `psutil` is installed.

## Supported formats

The open dialog filters for these extensions:

- `.m4b`
- `.mp3`
- `.mp4`
- `.m4a`
- `.aac`

Other formats supported by VLC may also work when chosen via the "All Files" option.

## Configuration files

User data is stored in `~/.config/m4bplayer/resume.dat`. This file is base64‑encoded JSON and is created automatically. You can wipe or inspect it from the **Settings** dialog inside the application.

## Contributing

Feel free to open issues or pull requests with improvements or bug fixes.
