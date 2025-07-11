#!/usr/bin/env python3
import sys, os, json, base64, subprocess
from pathlib import Path
from mutagen.mp4 import MP4
from mutagen import File as AFile
import vlc
from PyQt5 import QtCore, QtGui, QtWidgets
import pyttsx3  # for text-to-speech

# --- CONFIG & UTILITIES ---
HOME = Path.home()
CONFIG_DIR = HOME / '.config' / 'm4bplayer'
RESUME_DB = CONFIG_DIR / 'resume.dat'
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

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
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        QMessageBox.warning(None, "VLC Not Found",
            "Could not locate VLC libraries. Please select your VLC installation folder.")
        folder = QFileDialog.getExistingDirectory(None, "Select VLC install folder")
        if folder:
            os.environ['PATH'] += os.pathsep + folder
            try:
                return vlc.Instance('--no-video')
            except:
                QMessageBox.critical(None, "Error", "Failed to initialize VLC. Exiting.")
        sys.exit(1)

def find_ffprobe():
    cmd = 'ffprobe'
    try:
        subprocess.run([cmd, '-version'], capture_output=True, check=True)
        return cmd
    except:
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        QMessageBox.warning(None, "ffprobe Not Found",
            "ffprobe not found. Chapter support will be disabled.")
        path, _ = QFileDialog.getOpenFileName(None, "Locate ffprobe.exe", "", "Executable (*.exe)")
        return path or None

class Player(QtWidgets.QMainWindow):
    def __init__(self, vlc_inst, probe_cmd):
        super().__init__()
        self.vlc_inst, self.probe_cmd = vlc_inst, probe_cmd
        self.setWindowTitle("📚 Offline m4b Player")
        ico = Path(__file__).with_suffix('.ico')
        if ico.exists():
            self.setWindowIcon(QtGui.QIcon(str(ico)))
        self.setGeometry(100, 100, 900, 650)

        self.resume_db = load_resume()
        self.current_file = None
        self.chapters = []
        self.audio_tracks = []
        self.tts = pyttsx3.init()

        self._build_ui()
        self._apply_font_sizes()
        self._refresh_shelf()

        self.ui_timer = QtCore.QTimer(self)
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.start(200)

    def _build_ui(self):
        w = QtWidgets.QWidget()
        self.setCentralWidget(w)
        v = QtWidgets.QVBoxLayout(w)

        # File/Open/Settings
        hb = QtWidgets.QHBoxLayout()
        self.open_btn = QtWidgets.QPushButton("Open File…")
        self.open_btn.clicked.connect(self.open_file)
        hb.addWidget(self.open_btn)
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
        self.cover_lbl = QtWidgets.QLabel()
        self.cover_lbl.setFixedSize(100, 100)
        hb2.addWidget(self.cover_lbl)
        self.meta_lbl = QtWidgets.QLabel("No file loaded")
        hb2.addWidget(self.meta_lbl, 1)
        v.addLayout(hb2)

        # Playback Controls
        cb = QtWidgets.QHBoxLayout()
        for text, func in [("▶", self.play_pause),
                           ("« 10s", lambda: self.skip(-10000)),
                           ("10s »", lambda: self.skip(10000)),
                           ("Next Chapter", self.next_chapter)]:
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(func)
            cb.addWidget(btn)
        v.addLayout(cb)

        # Time slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setObjectName("timeSlider")
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

        # Volume slider
        vh = QtWidgets.QHBoxLayout()
        vh.addWidget(QtWidgets.QLabel("Volume:"))
        self.vol_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
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
        self.current_file = str(path)
        m = self.vlc_inst.media_new(self.current_file)
        self.player = self.vlc_inst.media_player_new()
        self.player.set_media(m)
        # preload & volume
        self.player.play(); QtCore.QThread.msleep(100); self.player.pause()
        self.player.audio_set_volume(self.resume_db.get('volume', 100))

        self._load_metadata(path)
        self._load_chapters(path)
        self._load_audio_streams()

        pos = self.resume_db.get(self.current_file, 0)
        self.player.set_time(pos)
        self.meta_lbl.setText(f"<b>{path.name}</b>")

        shelf = self.resume_db['__bookshelf__']
        if self.current_file not in shelf:
            shelf.append(self.current_file)
        save_resume(self.resume_db)
        self._refresh_shelf()
        self.play_pause_button().setText("▶")

    def _load_metadata(self, path: Path):
        self.meta_tree.clear()
        self.cover_lbl.clear()
        try:
            audio = MP4(str(path)) if path.suffix.lower() in ('.m4b', '.mp4', '.m4a') else AFile(str(path))
            tags = dict(audio.tags or {})
            cov = audio.tags.get('covr')
            if cov:
                data = cov[0] if isinstance(cov, list) else cov
                img = QtGui.QImage.fromData(data)
                pix = QtGui.QPixmap.fromImage(img).scaled(100, 100, QtCore.Qt.KeepAspectRatio)
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
        dlg.exec_()

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
                itm.setData(QtCore.Qt.UserRole, ms)
                self.ch_list.addItem(itm)
                self.chapters.append((ms, title))
        except:
            pass

    def _load_audio_streams(self):
        self.audio_tracks.clear()
        self.stream_combo.clear()
        descs = self.player.audio_get_track_description()
        if not descs:
            return
        for t in descs:
            tid, raw = (t if isinstance(t, tuple) else (t.id, t.name))
            if tid < 0:
                continue
            name = raw if isinstance(raw, str) else raw.decode('utf-8', errors='ignore')
            self.audio_tracks.append((tid, name))
            self.stream_combo.addItem(name)
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
        try:
            tid, _ = self.audio_tracks[idx]
            self.player.audio_set_track(tid)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Audio Stream Error", str(e))

    def on_time_edit(self):
        parts = self.time_edit.text().split(':')
        if len(parts) == 3:
            try:
                h, m, s = map(int, parts)
                ms = (h*3600 + m*60 + s) * 1000
                self.player.set_time(ms)
                length = self.player.get_length()
                if length > 0:
                    self.slider.setValue(int(ms/length * 1000))
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
        if self.player.is_playing():
            self.player.pause()
            self.play_btn.setText("▶")
        else:
            self.player.play()
            self.play_btn.setText("❚❚")

    def skip(self, msec):
        if self.current_file:
            t = self.player.get_time() + msec
            self.player.set_time(max(0, t))

    def next_chapter(self):
        now = self.player.get_time()
        for t, _ in self.chapters:
            if t > now:
                self.player.set_time(t)
                break

    def goto_chapter(self, item):
        self.player.set_time(item.data(QtCore.Qt.UserRole))

    def seek(self, pos):
        if self.current_file:
            self.player.set_position(pos/1000)

    def _update_ui(self):
        if not self.current_file:
            return
        self.slider.blockSignals(True)
        self.slider.setValue(int(self.player.get_position() * 1000))
        self.slider.blockSignals(False)
        if self.player.is_playing() and not self.time_edit.hasFocus():
            ms = self.player.get_time()
            s = ms // 1000
            self.time_edit.setText(f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}")
        self.resume_db[self.current_file] = self.player.get_time()
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
            itm.setData(QtCore.Qt.UserRole, p)
            self.shelf_list.addItem(itm)

    def _open_from_shelf(self, item):
        self.load_media(Path(item.data(QtCore.Qt.UserRole)))

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

        dlg.exec_()

    def _wipe_data(self):
        self.resume_db = {'__bookshelf__': [], 'ui_btn_size': 10, 'ui_title_size': 12, 'volume': 100}
        save_resume(self.resume_db)
        self._refresh_shelf()
        self._apply_font_sizes()

    def closeEvent(self, e):
        if self.current_file:
            self.resume_db[self.current_file] = self.player.get_time()
            save_resume(self.resume_db)
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
        QPushButton { border: none; padding: 5px; }
        QPushButton:hover { background-color: #555555; }
        QGroupBox::title { subcontrol-origin: margin; left: 7px; padding: 0 3px; }
    """)
    vlc_inst = find_vlc()
    probe_cmd = find_ffprobe()
    player = Player(vlc_inst, probe_cmd)
    player.show()
    sys.exit(app.exec_())
