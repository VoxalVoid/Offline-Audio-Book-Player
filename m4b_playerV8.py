#!/usr/bin/env python3
import sys, os, json, base64, subprocess
from pathlib import Path
import shutil
import math
import collections
try:
    import psutil  # optional resource monitoring
except ImportError:  # pragma: no cover - optional dependency
    psutil = None
missing_libs = []
try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional dependency
    pg = None
    missing_libs.append('pyqtgraph')
try:
    import numpy as np  # required by pyqtgraph
except ImportError:  # pragma: no cover - optional dependency
    np = None
    missing_libs.append('numpy')
try:
    import pyaudio
except ImportError:  # pragma: no cover - optional dependency
    pyaudio = None
    missing_libs.append('pyaudio')
if missing_libs:
    print('Missing packages:', ' '.join(missing_libs))
    print('Install them with: pip install ' + ' '.join(missing_libs))
from mutagen.mp4 import MP4
from mutagen import File as AFile
import vlc
from PyQt6 import QtCore, QtGui, QtWidgets
import pyttsx3  # for text-to-speech

# --- CONFIG & UTILITIES ---
HOME = Path.home()
CONFIG_DIR = HOME / '.config' / 'm4bplayer'
RESUME_DB = CONFIG_DIR / 'resume.dat'
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def _log_exception(exctype, value, tb):
    import traceback
    home = str(Path.home())
    trace = ''.join(traceback.format_exception(exctype, value, tb))
    sanitized = trace.replace(home, str(Path('C:/Users/USER')))
    print(sanitized, file=sys.stderr)

sys.excepthook = _log_exception

def load_resume():
    if not RESUME_DB.exists():
        return {'__bookshelf__': [], 'ui_btn_size': 10, 'ui_title_size': 12, 'volume': 100}
    try:
        raw = RESUME_DB.read_bytes()
        data = base64.b64decode(raw).decode()
        db = json.loads(data)
        db.setdefault('__bookshelf__', [])
        db.setdefault('ui_btn_size', 10)
        db.setdefault('ui_title_size', 12)
        db.setdefault('volume', 100)
        return db
    except:
        return {'__bookshelf__': [], 'ui_btn_size': 10, 'ui_title_size': 12, 'volume': 100}

def save_resume(db):
    b64 = base64.b64encode(json.dumps(db).encode())
    RESUME_DB.write_bytes(b64)

def find_vlc():
    try:
        return vlc.Instance('--no-video')
    except:
        QtWidgets.QMessageBox.warning(None, "VLC Not Found",
            "Could not locate VLC libraries. Please select your VLC installation folder.")
        folder = QtWidgets.QFileDialog.getExistingDirectory(None, "Select VLC install folder")
        if folder:
            os.environ['PATH'] += os.pathsep + folder
            try:
                return vlc.Instance('--no-video')
            except:
                QtWidgets.QMessageBox.critical(None, "Error", "Failed to initialize VLC. Exiting.")
        sys.exit(1)

def find_ffprobe():
    cmd = 'ffprobe'
    try:
        subprocess.run([cmd, '-version'], capture_output=True, check=True)
        return cmd
    except:
        QtWidgets.QMessageBox.warning(None, "ffprobe Not Found",
            "ffprobe not found. Chapter support will be disabled.")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Locate ffprobe.exe", "", "Executable (*.exe)")
        return path or None

def find_icon():
    base = Path(__file__).resolve().parent
    for p in [base / 'audio-book.ico', base / 'Images' / 'audio-book.ico', base.with_suffix('.ico')]:
        if p.exists():
            return p
    return None

class BookmarkDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Bookmarks")
        self.setStyleSheet(parent.styleSheet())
        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Book", "Time", "Note"])
        layout.addWidget(self.table)

        btns = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("Bookmark Current Time")
        self.load_btn = QtWidgets.QPushButton("Load Selected Bookmark")
        self.last_btn = QtWidgets.QPushButton("Load Last Time Stamp")
        self.del_btn = QtWidgets.QPushButton("Delete Selected")
        btns.addWidget(self.add_btn)
        btns.addWidget(self.load_btn)
        btns.addWidget(self.last_btn)
        btns.addWidget(self.del_btn)
        layout.addLayout(btns)

        self.add_btn.clicked.connect(self.add_bookmark)
        self.load_btn.clicked.connect(self.load_selected_from_button)
        self.last_btn.clicked.connect(lambda: parent.player.set_time(parent.prev_time))
        self.del_btn.clicked.connect(self.delete_selected)
        self.table.itemDoubleClicked.connect(self.load_selected)

        self.refresh()

    def fmt(self, ms):
        s = ms // 1000
        return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

    def refresh(self):
        self.table.setRowCount(0)
        for bm in self.parent.resume_db.get('__bookmarks__', []):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(Path(bm['file']).name[:30]))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(self.fmt(bm['pos'])))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(bm.get('note', '')))

    def add_bookmark(self):
        if not self.parent.current_file:
            return
        note, _ = QtWidgets.QInputDialog.getText(self, "Note", "Bookmark note:")
        bm = {'file': self.parent.current_file, 'pos': self.parent.player.get_time(), 'note': note}
        self.parent.resume_db.setdefault('__bookmarks__', []).append(bm)
        save_resume(self.parent.resume_db)
        self.refresh()

    def load_selected_from_button(self):
        rows = {i.row() for i in self.table.selectedItems()}
        if rows:
            self.load_bookmark(min(rows))

    def load_selected(self, item):
        self.load_bookmark(item.row())

    def load_bookmark(self, row):
        bms = self.parent.resume_db.get('__bookmarks__', [])
        if row >= len(bms):
            return
        bm = bms[row]
        if Path(bm['file']).exists():
            self.parent.prev_time = self.parent.player.get_time()
            self.parent.load_media(Path(bm['file']))
            self.parent.player.set_time(bm['pos'])
            self.parent.resume_db['__last_book__'] = bm['file']
            save_resume(self.parent.resume_db)

    def delete_selected(self):
        rows = sorted({i.row() for i in self.table.selectedItems()}, reverse=True)
        bms = self.parent.resume_db.get('__bookmarks__', [])
        for r in rows:
            if r < len(bms):
                bms.pop(r)
        save_resume(self.parent.resume_db)
        self.refresh()

# --- Extra UI Elements ----------------------------------------------------

class ClickableLabel(QtWidgets.QLabel):
    """QLabel emitting a clicked signal when pressed."""
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class GalleryDialog(QtWidgets.QDialog):
    """Dialog showing all images embedded in the book."""
    def __init__(self, images, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gallery")
        layout = QtWidgets.QVBoxLayout(self)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(container)
        self.labels = []
        for img in images:
            lbl = QtWidgets.QLabel()
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            lbl.orig = QtGui.QPixmap.fromImage(img)
            lbl.setPixmap(lbl.orig)
            self.vbox.addWidget(lbl)
            self.labels.append(lbl)
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def resizeEvent(self, e):
        for lbl in self.labels:
            if not lbl.orig.isNull():
                pix = lbl.orig.scaled(self.width()-40, self.height()-40,
                                       QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                       QtCore.Qt.TransformationMode.SmoothTransformation)
                lbl.setPixmap(pix)
        super().resizeEvent(e)


class VisualizerThread(QtCore.QThread):
    """Decode audio on the fly and emit level data."""

    level = QtCore.pyqtSignal(float)

    def __init__(self, path: Path, start_ms: int = 0, interval_ms: int = 100):
        super().__init__()
        self.path = path
        self.start_ms = start_ms
        self.interval_ms = interval_ms
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        ff = shutil.which("ffmpeg")
        if not ff or not self.path:
            return
        pos = str(self.start_ms / 1000.0)
        cmd = [ff, "-ss", pos, "-i", str(self.path), "-f", "s16le", "-ac", "1",
               "-ar", "8000", "-loglevel", "quiet", "-"]
        try:
            import audioop, time
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            buf = int(8000 * (self.interval_ms/1000.0) * 2)
            while self._running:
                data = proc.stdout.read(buf)
                if not data:
                    break
                rms = audioop.rms(data, 2) / 32768.0
                self.level.emit(rms)
            proc.stdout.close()
            proc.wait()
        except Exception:
            pass


class VisualizerWidget(QtWidgets.QWidget):
    """Display audio levels fed from a background thread."""

    def __init__(self, player, interval_ms=100):
        super().__init__()
        self.player = player
        self.interval_ms = interval_ms
        self.mode = 0
        self.data = collections.deque([0]*200, maxlen=200)
        self.current_level = 0.0

        layout = QtWidgets.QVBoxLayout(self)
        if pg is None or np is None:
            txt = QtWidgets.QLabel("Install pyqtgraph numpy pyaudio for visualizers")
            layout.addWidget(txt)
            self.res_label = QtWidgets.QLabel()
            layout.addWidget(self.res_label)
            self.timer = QtCore.QTimer(self)
            self.timer.timeout.connect(self._update_stats)
            self.timer.start(self.interval_ms)
            return

        self.plot = pg.PlotWidget(background="#222")
        self.plot.setYRange(-1, 1)
        layout.addWidget(self.plot, 1)
        self.line = self.plot.plot(pen='m')
        self.bar_item = pg.BarGraphItem(x=[], height=[], width=0.8, brush='y')
        self.plot.addItem(self.bar_item)
        self.bar_item.hide()
        self.curve = self.line  # backward compat
        self.res_label = QtWidgets.QLabel()
        layout.addWidget(self.res_label)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._update_plot)
        self.timer.start(self.interval_ms)
        self.set_mode(self.mode)

    @QtCore.pyqtSlot(float)
    def add_level(self, level: float):
        """Receive a new audio level from the worker thread."""
        self.current_level = max(-1.0, min(1.0, level))

    def _update_stats(self):
        if psutil:
            p = psutil.Process()
            mem = p.memory_info().rss / 1e6
            cpu = psutil.cpu_percent(interval=None)
            self.res_label.setText(f"CPU: {cpu:.1f}%  RAM: {mem:.1f} MB  Threads: {p.num_threads()}")

    def _update_plot(self):
        self._update_stats()
        if pg is None or np is None:
            return
        self.data.append(self.current_level)
        arr = np.array(self.data)
        if self.mode == 0:
            x = np.arange(len(arr))
            self.line.setData(x, arr)
        elif self.mode == 1:
            x = np.arange(len(arr))
            self.bar_item.setOpts(x=x, height=arr)
        else:
            theta = np.linspace(0, 2*np.pi, len(arr), endpoint=False)
            r = 0.5 + arr
            x = r * np.cos(theta)
            y = r * np.sin(theta)
            self.line.setData(x, y)

    def set_mode(self, idx):
        self.mode = idx
        if pg is None or np is None:
            return
        if self.mode == 0:
            self.bar_item.hide()
            self.line.show()
            self.line.setPen('m')
            self.line.setSymbol(None)
        elif self.mode == 1:
            self.line.hide()
            self.bar_item.show()
        else:
            self.bar_item.hide()
            self.line.show()
            self.line.setPen(None)
            self.line.setSymbol('o')
            self.line.setSymbolSize(5)
            self.line.setSymbolBrush('c')

    def closeEvent(self, e):
        if hasattr(self.player, '_stop_vis_thread'):
            self.player._stop_vis_thread()
        super().closeEvent(e)


class VisualizerWindow(QtWidgets.QDialog):
    def __init__(self, player):
        super().__init__()
        self.player = player
        self.setWindowTitle("Visualizer")
        layout = QtWidgets.QVBoxLayout(self)
        self.widget = VisualizerWidget(player)
        layout.addWidget(self.widget, 1)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["Wave", "Bars", "Circle"])
        self.mode_combo.currentIndexChanged.connect(self.widget.set_mode)
        layout.addWidget(self.mode_combo)
        self.resize(500, 500)

    def closeEvent(self, e):
        if hasattr(self.player, '_stop_vis_thread'):
            self.player._stop_vis_thread()
        super().closeEvent(e)

class Player(QtWidgets.QMainWindow):
    def __init__(self, vlc_inst, probe_cmd):
        super().__init__()
        self.vlc_inst, self.probe_cmd = vlc_inst, probe_cmd
        self.setWindowTitle("📚 Offline m4b Player")
        ico_path = find_icon()
        if ico_path:
            icon = QtGui.QIcon(str(ico_path))
        else:
            icon = self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
        self.setWindowIcon(icon)
        self.setGeometry(100, 100, 900, 650)

        # ensure the media player object exists
        self.player = self.vlc_inst.media_player_new()

        self.resume_db = load_resume()
        self.resume_db.setdefault('__bookmarks__', [])
        self.current_file = None
        self.chapters = []
        self.audio_tracks = []
        self.tts = pyttsx3.init()
        self.prev_time = 0
        self.play_btn = None
        self.images = []
        self.vis_win = None
        self.vis_thread = None

        self._build_ui()
        self._apply_font_sizes()
        self._refresh_shelf()
        self.compact = False
        self.prev_geom = None
        self._load_last_book()

        self.ui_timer = QtCore.QTimer(self)
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.start(200)

    def _build_ui(self):
        w = QtWidgets.QWidget()
        self.setCentralWidget(w)
        v = QtWidgets.QVBoxLayout(w)

        # File/Open/Visualizer/Settings
        hb = QtWidgets.QHBoxLayout()
        self.open_btn = QtWidgets.QPushButton("Open File…")
        self.open_btn.clicked.connect(self.open_file)
        hb.addWidget(self.open_btn)
        self.vis_btn = QtWidgets.QPushButton("Visualizer")
        self.vis_btn.clicked.connect(self.open_visualizer)
        hb.addWidget(self.vis_btn)
        self.settings_btn = QtWidgets.QPushButton("⚙ Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        hb.addWidget(self.settings_btn)
        v.addLayout(hb)

        # Bookshelf
        v.addWidget(QtWidgets.QLabel("📚 Bookshelf"))
        self.shelf_list = QtWidgets.QListWidget()
        self.shelf_list.itemClicked.connect(self._open_from_shelf)
        v.addWidget(self.shelf_list)

        # Cover + title
        hb2 = QtWidgets.QHBoxLayout()
        self.cover_lbl = ClickableLabel()
        self.cover_lbl.setFixedSize(100, 100)
        self.cover_lbl.clicked.connect(self.open_gallery)
        hb2.addWidget(self.cover_lbl)
        self.meta_lbl = QtWidgets.QLabel("No file loaded")
        hb2.addWidget(self.meta_lbl, 1)
        v.addLayout(hb2)

        # Playback Controls
        cb = QtWidgets.QHBoxLayout()
        for text, func in [("▶", self.play_pause),
                           ("« 10s", lambda: self.skip(-10000)),
                           ("10s »", lambda: self.skip(10000)),
                           ("Bookmarks", self.open_bookmarks)]:
            btn = QtWidgets.QPushButton(text)
            if text == "▶":
                self.play_btn = btn
            btn.clicked.connect(func)
            cb.addWidget(btn)
        v.addLayout(cb)

        # Time slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setObjectName("timeSlider")
        self.slider.setRange(0, 1)
        self.slider.sliderMoved.connect(self.seek)
        v.addWidget(self.slider)

        # Time edit + Go
        th = QtWidgets.QHBoxLayout()
        th.addWidget(QtWidgets.QLabel("Time:"))
        self.time_edit = QtWidgets.QLineEdit("00:00:00")
        self.time_edit.setFixedWidth(100)
        th.addWidget(self.time_edit)
        go = QtWidgets.QPushButton("Go")
        go.setFixedWidth(40)
        go.clicked.connect(self.on_time_edit)
        th.addWidget(go)
        v.addLayout(th)
        self.continue_lbl = QtWidgets.QLabel("Continue From: 00:00:00")
        v.addWidget(self.continue_lbl)

        # Volume slider
        vh = QtWidgets.QHBoxLayout()
        vh.addWidget(QtWidgets.QLabel("Volume:"))
        self.vol_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.vol_slider.setObjectName("volumeSlider")
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(self.resume_db.get('volume', 100))
        self.vol_slider.valueChanged.connect(self._on_volume_slider)
        vh.addWidget(self.vol_slider)
        self.vol_edit = QtWidgets.QLineEdit(str(self.resume_db.get('volume', 100)))
        self.vol_edit.setFixedWidth(50)
        self.vol_edit.editingFinished.connect(self._on_volume_edit)
        vh.addWidget(self.vol_edit)
        v.addLayout(vh)

        # Audio streams
        sh = QtWidgets.QHBoxLayout()
        sh.addWidget(QtWidgets.QLabel("Audio Stream:"))
        self.stream_combo = QtWidgets.QComboBox()
        self.stream_combo.currentIndexChanged.connect(self._change_audio_stream)
        sh.addWidget(self.stream_combo)
        v.addLayout(sh)

        # Chapters
        v.addWidget(QtWidgets.QLabel("Chapters"))
        self.ch_list = QtWidgets.QListWidget()
        self.ch_list.itemClicked.connect(self.goto_chapter)
        v.addWidget(self.ch_list)

        # Metadata dropdown
        self.meta_box = QtWidgets.QGroupBox("Show Metadata ▶")
        self.meta_box.setCheckable(True)
        self.meta_box.setChecked(False)
        self.meta_box.toggled.connect(self._toggle_meta)
        mv = QtWidgets.QVBoxLayout(self.meta_box)
        self.meta_tree = QtWidgets.QTreeWidget()
        self.meta_tree.setHeaderLabels(["Field", "Value"])
        self.meta_tree.setUniformRowHeights(True)
        self.meta_tree.itemDoubleClicked.connect(self._show_meta_full)
        mv.addWidget(self.meta_tree)
        v.addWidget(self.meta_box)
        self.meta_tree.hide()

    def _apply_font_sizes(self):
        bsz = self.resume_db.get('ui_btn_size', 10)
        tsz = self.resume_db.get('ui_title_size', 12)
        for btn in self.findChildren(QtWidgets.QPushButton):
            f = btn.font(); f.setPointSize(bsz); btn.setFont(f)
        for lbl in self.findChildren(QtWidgets.QLabel):
            f = lbl.font(); f.setPointSize(tsz); lbl.setFont(f)

    def open_file(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Audio File", "",
            "Audio/Video Files (*.m4b *.mp3 *.mp4 *.m4a *.aac);;All Files (*)")
        if f:
            self.load_media(Path(f))

    def load_media(self, path: Path):
        if hasattr(self, 'player') and self.player is not None:
            try:
                self.player.stop()
            except Exception:
                pass
        self.current_file = str(path)
        m = self.vlc_inst.media_new(self.current_file)
        self.player = self.vlc_inst.media_player_new()
        self.player.set_media(m)
        # preload & volume
        self.player.play(); QtCore.QThread.msleep(200); self.player.pause()
        self.player.audio_set_volume(self.resume_db.get('volume', 100))
        if self.vis_thread:
            self.vis_thread.stop()
            self.vis_thread.wait()
            self.vis_thread = None
        if self.vis_win:
            self.vis_win.widget.setParent(None)
            self.vis_win.widget = VisualizerWidget(self)
            self.vis_win.layout().insertWidget(0, self.vis_win.widget, 1)
            try:
                self.vis_win.mode_combo.currentIndexChanged.disconnect()
            except TypeError:
                pass
            self.vis_win.mode_combo.currentIndexChanged.connect(self.vis_win.widget.set_mode)
            self.vis_win.widget.set_mode(self.vis_win.mode_combo.currentIndex())
            self._start_vis_thread()
        length = self.player.get_length()
        self.slider.setRange(0, length or 1)

        self._load_metadata(path)
        if hasattr(self, '_load_chapters'):
            self._load_chapters(path)
        if hasattr(self, '_load_audio_streams'):
            self._load_audio_streams()

        pos = self.resume_db.get(self.current_file, 0)
        self.player.set_time(pos)
        self.continue_lbl.setText(f"Continue From: {pos//3600000:02d}:{(pos//60000)%60:02d}:{(pos//1000)%60:02d}")
        self.meta_lbl.setText(f"<b>{path.name}</b>")

        self.resume_db['__last_book__'] = self.current_file

        shelf = self.resume_db['__bookshelf__']
        if self.current_file not in shelf:
            shelf.append(self.current_file)
        save_resume(self.resume_db)
        self._refresh_shelf()
        if self.play_btn:
            self.play_btn.setText("▶")

    def _load_metadata(self, path: Path):
        self.meta_tree.clear()
        self.cover_lbl.clear()
        self.images = []
        try:
            audio = MP4(str(path)) if path.suffix.lower() in ('.m4b', '.mp4', '.m4a') else AFile(str(path))
            tags = dict(audio.tags or {})
            cov = audio.tags.get('covr')
            if cov:
                imgs = cov if isinstance(cov, list) else [cov]
                for data in imgs:
                    qimg = QtGui.QImage.fromData(bytes(data))
                    if not qimg.isNull():
                        self.images.append(qimg)
                if self.images:
                    pix = QtGui.QPixmap.fromImage(self.images[0]).scaled(100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
                    self.cover_lbl.setPixmap(pix)
            for k, v in tags.items():
                text = str(v)
                if k == 'covr' and len(text) > 300:
                    text = text[:300] + '…'
                QtWidgets.QTreeWidgetItem(self.meta_tree, [k, text])
        except:
            pass


    def _show_meta_full(self, item, _):
        key, val = item.text(0), item.text(1)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(key)
        ly = QtWidgets.QVBoxLayout(dlg)
        txt = QtWidgets.QTextEdit(val)
        txt.setReadOnly(True)
        ly.addWidget(txt)
        if key.lower() in ('desc', 'description'):
            btn = QtWidgets.QPushButton("Read Text")
            btn.clicked.connect(lambda: self.tts.say(txt.toPlainText()) or self.tts.runAndWait())
            ly.addWidget(btn)
        dlg.resize(400, 300)
        dlg.exec()

    def _load_chapters(self, path: Path):
        self.chapters.clear()
        self.ch_list.clear()
        if not self.probe_cmd:
            return
        try:
            res = subprocess.run(
                [self.probe_cmd, '-v', 'quiet', '-print_format', 'json', '-show_chapters', str(path)],
                capture_output=True, check=True)
            obj = json.loads(res.stdout)
            for c in obj.get('chapters', []):
                ms = int(float(c['start_time']) * 1000)
                title = c.get('tags', {}).get('title', f"Chapter {len(self.chapters)+1}")
                itm = QtWidgets.QListWidgetItem(f"{ms//60000}:{(ms//1000)%60:02d}  {title}")
                itm.setData(QtCore.Qt.ItemDataRole.UserRole, ms)
                self.ch_list.addItem(itm)
                self.chapters.append((ms, title))
        except:
            pass

    def _load_audio_streams(self):
        self.audio_tracks.clear()
        self.stream_combo.blockSignals(True)
        self.stream_combo.clear()
        self.stream_combo.blockSignals(False)
        descs = self.player.audio_get_track_description()
        if not descs:
            QtCore.QTimer.singleShot(300, self._load_audio_streams)
            return
        self.stream_combo.blockSignals(True)
        for t in descs:
            tid, raw = (t if isinstance(t, tuple) else (t.id, t.name))
            if tid < 0:
                continue
            name = raw if isinstance(raw, str) else raw.decode('utf-8', errors='ignore')
            self.audio_tracks.append((tid, name))
            self.stream_combo.addItem(name)
        self.stream_combo.blockSignals(False)
        cur = self.player.audio_get_track()
        if cur < 0 and self.audio_tracks:
            self.player.audio_set_track(self.audio_tracks[0][0])
            self.stream_combo.setCurrentIndex(0)
        else:
            for i, (tid, _) in enumerate(self.audio_tracks):
                if tid == cur:
                    self.stream_combo.setCurrentIndex(i)
                    break

    def _change_audio_stream(self, idx):
        if 0 <= idx < len(self.audio_tracks):
            tid, _ = self.audio_tracks[idx]
            self.player.audio_set_track(tid)

    def on_time_edit(self):
        parts = self.time_edit.text().split(':')
        if len(parts) == 3:
            try:
                h, m, s = map(int, parts)
                ms = (h*3600 + m*60 + s) * 1000
                self.player.set_time(ms)
                length = self.player.get_length()
                if length > 0:
                    self.slider.setRange(0, length)
                    self.slider.setValue(ms)
            except:
                pass

    def _on_volume_slider(self, val):
        self.player.audio_set_volume(val)
        self.vol_edit.setText(str(val))
        self.resume_db['volume'] = val
        save_resume(self.resume_db)

    def _on_volume_edit(self):
        try:
            val = int(self.vol_edit.text())
        except:
            val = self.resume_db.get('volume', 100)
        if val > 200:
            val = 100
            QtWidgets.QMessageBox.information(self, "Volume", "Resetting to 100.")
        elif val > 100:
            QtWidgets.QMessageBox.warning(self, "Warning", "High volume can damage hearing.")
        self.player.audio_set_volume(val)
        self.vol_slider.setValue(min(val, 100))
        self.vol_edit.setText(str(val))
        self.resume_db['volume'] = val
        save_resume(self.resume_db)

    def play_pause(self):
        if not self.current_file:
            QtWidgets.QMessageBox.information(self, "No Book Loaded", "Please open an audio book first.")
            return
        if self.player.is_playing():
            self.player.pause()
            self.play_btn.setText("▶")
            self._stop_vis_thread()
        else:
            self.player.play()
            self.play_btn.setText("❚❚")
            self._start_vis_thread()

    def skip(self, msec):
        if self.current_file:
            t = self.player.get_time() + msec
            self.player.set_time(max(0, t))
            if self.player.is_playing():
                self._start_vis_thread()

    def next_chapter(self):
        now = self.player.get_time()
        for t, _ in self.chapters:
            if t > now:
                self.player.set_time(t)
                break

    def goto_chapter(self, item):
        self.player.set_time(item.data(QtCore.Qt.ItemDataRole.UserRole))
        if self.player.is_playing():
            self._start_vis_thread()

    def seek(self, pos):
        if self.current_file:
            self.player.set_time(pos)
            if self.player.is_playing():
                self._start_vis_thread()

    def _update_ui(self):
        if not self.current_file:
            return
        self.slider.blockSignals(True)
        ms = self.player.get_time()
        self.slider.setValue(ms)
        self.slider.blockSignals(False)
        if self.player.is_playing() and not self.time_edit.hasFocus():
            s = ms // 1000
            self.time_edit.setText(f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}")
        self.resume_db[self.current_file] = self.player.get_time()
        self.continue_lbl.setText(f"Continue From: {ms//3600000:02d}:{(ms//60000)%60:02d}:{(ms//1000)%60:02d}")
        save_resume(self.resume_db)

    def _toggle_meta(self, show):
        self.meta_box.setTitle("Hide Metadata ▼" if show else "Show Metadata ▶")
        self.meta_tree.setVisible(show)

    def _refresh_shelf(self):
        self.shelf_list.clear()
        valid = [p for p in self.resume_db['__bookshelf__'] if Path(p).exists()]
        self.resume_db['__bookshelf__'] = valid
        save_resume(self.resume_db)
        for p in valid:
            itm = QtWidgets.QListWidgetItem(Path(p).name)
            itm.setData(QtCore.Qt.ItemDataRole.UserRole, p)
            self.shelf_list.addItem(itm)

    def _open_from_shelf(self, item):
        self.load_media(Path(item.data(QtCore.Qt.ItemDataRole.UserRole)))

    # removed system tray support

    def changeEvent(self, e):
        if e.type() == QtCore.QEvent.Type.WindowStateChange and self.isMinimized():
            QtCore.QTimer.singleShot(0, self._enter_compact)
        super().changeEvent(e)

    def _enter_compact(self):
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowState.WindowMinimized)
        if not self.compact:
            self.prev_geom = self.geometry()
            self.compact = True
        self.resize(300, 150)
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 20,
                  screen.bottom() - self.height() - 20)

    def mouseDoubleClickEvent(self, e):
        if self.compact:
            self._exit_compact()
        else:
            super().mouseDoubleClickEvent(e)

    def _exit_compact(self):
        if self.compact and self.prev_geom:
            self.setGeometry(self.prev_geom)
            self.compact = False

    def _load_last_book(self):
        last = self.resume_db.get('__last_book__')
        if last:
            p = Path(last)
            if p.exists():
                self.load_media(p)
            else:
                QtWidgets.QMessageBox.information(self, "Missing Book", "Last book not found. Please open a file.")

    def open_bookmarks(self):
        dlg = BookmarkDialog(self)
        dlg.exec()

    def open_gallery(self):
        if not self.images:
            return
        dlg = GalleryDialog(self.images, self)
        dlg.resize(400, 300)
        dlg.exec()

    def open_visualizer(self):
        if self.vis_win is None:
            self.vis_win = VisualizerWindow(self)
        else:
            self.vis_win.widget.setParent(None)
            self.vis_win.widget = VisualizerWidget(self)
            self.vis_win.layout().insertWidget(0, self.vis_win.widget, 1)
            try:
                self.vis_win.mode_combo.currentIndexChanged.disconnect()
            except TypeError:
                pass
            self.vis_win.mode_combo.currentIndexChanged.connect(self.vis_win.widget.set_mode)
            self.vis_win.widget.set_mode(self.vis_win.mode_combo.currentIndex())
        self.vis_win.show()
        self.vis_win.raise_()
        self._start_vis_thread()

    def _start_vis_thread(self):
        if self.vis_win is None or pg is None or np is None:
            return
        if not self.current_file:
            return
        if self.vis_thread:
            self.vis_thread.stop()
            self.vis_thread.wait()
        self.vis_thread = VisualizerThread(Path(self.current_file), self.player.get_time())
        self.vis_thread.level.connect(self.vis_win.widget.add_level)
        self.vis_thread.start()

    def _stop_vis_thread(self):
        if self.vis_thread:
            self.vis_thread.stop()
            self.vis_thread.wait()
            self.vis_thread = None

    def open_settings(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Settings")
        layout = QtWidgets.QVBoxLayout(dlg)

        for txt, fn in [("Wipe All Data", self._wipe_data),
                        ("View All Data", None),
                        ("Export All Data", None),
                        ("Import All Data", None)]:
            btn = QtWidgets.QPushButton(txt)
            layout.addWidget(btn)
            if fn:
                btn.clicked.connect(fn)

        chk = QtWidgets.QCheckBox("Decrypt and show all data")
        chk.setChecked(True)
        txtbox = QtWidgets.QTextEdit()
        txtbox.setReadOnly(True)
        layout.addWidget(chk)
        layout.addWidget(txtbox)
        layout.itemAt(1).widget().clicked.connect(
            lambda: txtbox.setText(
                json.dumps(self.resume_db, indent=2)
                if chk.isChecked()
                else RESUME_DB.read_bytes().decode(errors='ignore')
            )
        )

        layout.addWidget(QtWidgets.QLabel("UI Settings:"))
        btn_spin = QtWidgets.QSpinBox(); btn_spin.setRange(6,32); btn_spin.setValue(self.resume_db['ui_btn_size'])
        lbl_spin = QtWidgets.QSpinBox(); lbl_spin.setRange(6,32); lbl_spin.setValue(self.resume_db['ui_title_size'])
        r1 = QtWidgets.QHBoxLayout(); r1.addWidget(QtWidgets.QLabel("Button font size:")); r1.addWidget(btn_spin); layout.addLayout(r1)
        r2 = QtWidgets.QHBoxLayout(); r2.addWidget(QtWidgets.QLabel("Title font size:")); r2.addWidget(lbl_spin); layout.addLayout(r2)
        btn_spin.valueChanged.connect(lambda v: (self.resume_db.__setitem__('ui_btn_size', v), save_resume(self.resume_db), self._apply_font_sizes()))
        lbl_spin.valueChanged.connect(lambda v: (self.resume_db.__setitem__('ui_title_size', v), save_resume(self.resume_db), self._apply_font_sizes()))

        dlg.exec()

    def _wipe_data(self):
        self.resume_db = {'__bookshelf__': [], 'ui_btn_size': 10, 'ui_title_size': 12, 'volume': 100}
        save_resume(self.resume_db)
        self._refresh_shelf()
        self._apply_font_sizes()

    def closeEvent(self, e):
        if self.current_file:
            self.resume_db[self.current_file] = self.player.get_time()
            self.resume_db['__last_book__'] = self.current_file
            save_resume(self.resume_db)
        self._stop_vis_thread()
        super().closeEvent(e)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet("""
        QSlider#timeSlider::groove:horizontal { height: 8px; }
        QSlider#volumeSlider::groove:horizontal { height: 4px; }
        QWidget { background-color: #2d2d2d; color: white; }
        QMainWindow { background-color: #2d2d2d; }
        QLabel, QListWidget, QPushButton, QGroupBox, QTreeWidget { background-color: #2d2d2d; color: white; }
        QDialog, QTextEdit, QSpinBox, QLineEdit { background-color: #222222; color: white; }
        QListWidget::item:selected { background-color: #555555; }
        QPushButton { background-color: #3b3b3b; border: 1px solid #777; padding: 5px; border-radius: 3px; }
        QPushButton:hover { background-color: #555555; }
        QGroupBox::title { subcontrol-origin: margin; left: 7px; padding: 0 3px; }
    """)
    vlc_inst = find_vlc()
    probe_cmd = find_ffprobe()
    player = Player(vlc_inst, probe_cmd)
    player.show()
    sys.exit(app.exec())
