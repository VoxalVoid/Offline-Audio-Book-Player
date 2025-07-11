# Offline Audio Book Player
A lightweight PyQt5 application for listening to audio books without an internet connection. It is written in a single Python file and relies on VLC for playback. The program runs entirely offline and focuses on `.m4b` books but can open several common audio formats. Playback history and bookmarks are stored under `~/.config/m4bplayer` (or `%USERPROFILE%\.config\m4bplayer` on Windows).

## Features

- Resume playback from your last position for every book
- Built‑in "Bookshelf" listing previously opened files
- Chapter list when `ffprobe` is available
- Switch between audio tracks if the media provides multiple streams
- Displays metadata and cover art
- Small settings dialog to adjust font sizes and clear stored data
- Bookmark dialog to save and load timestamps with notes
- System tray icon so playback can continue in the background
- Slider adjusts to long books and shows a "Continue From" label
- Automatically reopens the last book when the program starts
=======

## Requirements

- Python 3.7 or newer
- [VLC](https://www.videolan.org/) installed so that the `libvlc` libraries are discoverable
- [`ffprobe`](https://ffmpeg.org/ffprobe.html) (part of FFmpeg) for reading chapter information
- Python packages: `mutagen`, `python-vlc`, `PyQt5`, `pyttsx3`

Install the Python dependencies with:

```bash
pip install mutagen python-vlc PyQt5 pyttsx3
```

## Windows 11 Setup

On Windows 11 the player works the same way as on Linux or macOS but the dependencies must be installed manually:

1. Install [Python 3](https://www.python.org/downloads/windows/) and enable the *Add Python to PATH* option.
2. Install [VLC](https://www.videolan.org/) for Windows (64‑bit recommended).
3. Download a static build of [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) and extract `ffprobe.exe`. Add the folder containing `ffprobe.exe` to your `PATH` (or point the application to it when prompted).
4. Open **PowerShell** or **Command Prompt** and run:

```powershell
pip install mutagen python-vlc PyQt5 pyttsx3
```

Run the application from the same terminal with:

```powershell
python m4b_playerV6.py
```

The configuration file will be created under `%USERPROFILE%\.config\m4bplayer\resume.dat`.

## Usage

Run the application with Python. On most Linux or macOS systems the command is `python3`, while on Windows you typically use `python`:

```bash
python m4b_playerV6.py
```

On first start, the player creates a `resume.dat` file inside the `~/.config/m4bplayer` folder (or `%USERPROFILE%\.config\m4bplayer` on Windows) to store progress, bookshelf entries and UI preferences. If VLC or ffprobe cannot be located automatically, you will be prompted to select their locations.

=======
## Usage

Run the application with Python:

```bash
python3 m4b_playerV5.py
```

On first start, the player creates `~/.config/m4bplayer/resume.dat` to store progress, bookshelf entries and UI preferences. If VLC or ffprobe cannot be located automatically, you will be prompted to select their locations.

## Supported formats

The open dialog filters for these extensions:

- `.m4b`
- `.mp3`
- `.mp4`
- `.m4a`
- `.aac`

Other formats supported by VLC may also work when chosen via the "All Files" option.

## Configuration files

User data is stored in `~/.config/m4bplayer/resume.dat` on Linux and macOS or `%USERPROFILE%\.config\m4bplayer\resume.dat` on Windows. This file is base64‑encoded JSON and is created automatically. You can wipe or inspect it from the **Settings** dialog inside the application.

=======
User data is stored in `~/.config/m4bplayer/resume.dat`. This file is base64‑encoded JSON and is created automatically. You can wipe or inspect it from the **Settings** dialog inside the application.

## Contributing

Feel free to open issues or pull requests with improvements or bug fixes.
