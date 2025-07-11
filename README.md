# Offline Audio Book Player

A lightweight PyQt5 application for listening to audio books without an internet connection. It is written in a single Python file and relies on VLC for playback. The player focuses on `.m4b` books but can open several common audio formats.

## Features

- Resume playback from your last position for every book
- Built‑in "Bookshelf" listing previously opened files
- Chapter list when `ffprobe` is available
- Switch between audio tracks if the media provides multiple streams
- Displays metadata and cover art
- Small settings dialog to adjust font sizes and clear stored data

## Requirements

- Python 3.7 or newer
- [VLC](https://www.videolan.org/) installed so that the `libvlc` libraries are discoverable
- [`ffprobe`](https://ffmpeg.org/ffprobe.html) (part of FFmpeg) for reading chapter information
- Python packages: `mutagen`, `python-vlc`, `PyQt5`, `pyttsx3`

Install the Python dependencies with:

```bash
pip install mutagen python-vlc PyQt5 pyttsx3
```

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

User data is stored in `~/.config/m4bplayer/resume.dat`. This file is base64‑encoded JSON and is created automatically. You can wipe or inspect it from the **Settings** dialog inside the application.

## Contributing

Feel free to open issues or pull requests with improvements or bug fixes.
