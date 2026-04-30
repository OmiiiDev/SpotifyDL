import sys
import os
import re
import threading
import subprocess
import json
import datetime
import urllib.request
import platform
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QLineEdit, QProgressBar, QTextEdit, 
                            QFileDialog, QMessageBox, QTabWidget, QComboBox, QSlider,
                            QCheckBox, QSpinBox, QGroupBox, QRadioButton, QSplitter,
                            QListWidget, QListWidgetItem, QDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QIcon, QPixmap, QFont, QDesktopServices


class DownloadWorker(QThread):
    update_console = pyqtSignal(str)
    update_progress = pyqtSignal(int, int)
    download_complete = pyqtSignal(bool, str, str, str)
    
    def __init__(self, url, download_path, quality, format_type, use_auth, auth_token=""):
        super().__init__()
        self.url = url
        self.download_path = download_path
        self.quality = quality
        self.format_type = format_type
        self.use_auth = use_auth
        self.auth_token = auth_token
        
    def run(self):
        if not self.url:
            self.download_complete.emit(False, "No URL provided", "", "")
            return

        # Change to download directory
        original_dir = os.getcwd()
        os.chdir(self.download_path)

        # Get executable paths - try multiple methods to find them
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        current_dir = os.getcwd()
        
        # Get locations for ffmpeg and spotdl (for portable version)
        possible_ffmpeg_paths = [
            os.path.join(os.path.abspath(os.path.dirname(__file__)), 'ffmpeg.exe')
        ]
        
        possible_spotdl_paths = [
            os.path.join(os.path.abspath(os.path.dirname(__file__)), 'spotdl.exe')
        ]
        
        # Find ffmpeg
        ffmpeg_path = None
        for path in possible_ffmpeg_paths:
            if os.path.isfile(path):
                ffmpeg_path = path
                break
                
        # Find spotdl
        spotdl_path = None
        for path in possible_spotdl_paths:
            if os.path.isfile(path):
                spotdl_path = path
                break
        
        # Check if executables were found
        if not ffmpeg_path:
            self.download_complete.emit(False, "ffmpeg.exe not found. Make sure it's in the same directory as the application.", self.url, "")
            os.chdir(original_dir)
            return
            
        if not spotdl_path:
            self.download_complete.emit(False, "spotdl.exe not found. Make sure it's in the same directory as the application.", self.url, "")
            os.chdir(original_dir)
            return
        
        # Download command
        command = [spotdl_path, "download", self.url, "--bitrate", self.quality, "--ffmpeg", ffmpeg_path]
        
        if self.format_type != "mp3":
            command.extend(["--output-format", self.format_type])
            
        if self.use_auth:
            command.append("--user-auth")

        if self.auth_token and self.auth_token.strip():
            command.extend(["--auth-token", self.auth_token.strip()])
        
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                **({'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {})
            )
            
            total_tracks = 1
            current_track = 0
            downloaded_tracks = []
            
            for line in process.stdout:
                # Only show relevant download information, not debug info
                if "Downloading" in line or "Found" in line or "Downloaded" in line or "Error" in line:
                    self.update_console.emit(line.strip())
                
                if "Downloading" in line:
                    current_track += 1
                    self.update_progress.emit(current_track, total_tracks)
                    
                    
                    track_match = re.search(r"Downloading (.+)", line)
                    if track_match:
                        downloaded_tracks.append(track_match.group(1).strip())
                        
                elif "Found" in line:
                    match = re.search(r"Found (\d+) tracks", line)
                    if match:
                        total_tracks = int(match.group(1))

            return_code = process.wait()
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if return_code == 0:
                # Create a summary of downloaded tracks
                track_summary = ", ".join(downloaded_tracks) if downloaded_tracks else self.url
                self.download_complete.emit(True, "Download completed successfully!", track_summary, timestamp)
            else:
                self.download_complete.emit(False, f"Download failed with return code {return_code}.", self.url, timestamp)
        except Exception as e:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.download_complete.emit(False, str(e), self.url, timestamp)
        finally:
            # Return to original directory
            os.chdir(original_dir)


class SpotifyDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotify Downloader Pro")
        self.setMinimumSize(800, 765)
        
        # Create app data directory in %APPDATA%
        self.app_data_dir = os.path.join(os.getenv('APPDATA'), "SpotifyDownloaderPro")
        if not os.path.exists(self.app_data_dir):
            os.makedirs(self.app_data_dir)
        
        # Download history
        self.history_file = os.path.join(self.app_data_dir, "download_history.json")
        self.download_history = self.load_history()
        
        # Settings file
        self.settings_file = os.path.join(self.app_data_dir, "settings.json")
        self.settings = self.load_settings()
        
        # Set the application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121212;
                color: #FFFFFF;
            }
            QTabWidget {
                background-color: #121212;
            }
            QTabWidget::pane {
                border: 1px solid #333333;
                background-color: #1E1E1E;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #282828;
                color: #BBBBBB;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #1E1E1E;
                color: #1DB954;
                border-bottom: 2px solid #1DB954;
            }
            QWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
            }
            QLineEdit, QTextEdit, QComboBox, QListWidget {
                background-color: #282828;
                color: #FFFFFF;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton {
                background-color: #1DB954;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ED760;
            }
            QPushButton:pressed {
                background-color: #1AA34A;
            }
            QPushButton:disabled {
                background-color: #565656;
                color: #888888;
            }
            QProgressBar {
                border: 1px solid #333333;
                border-radius: 4px;
                text-align: center;
                background-color: #282828;
            }
            QProgressBar::chunk {
                background-color: #1DB954;
                border-radius: 3px;
            }
            QGroupBox {
                border: 1px solid #333333;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                color: #1DB954;
            }
            QCheckBox, QRadioButton {
                color: #FFFFFF;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #333333;
                height: 8px;
                background: #282828;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #1DB954;
                border: 1px solid #1DB954;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 1px;
                border-left-color: #333333;
                border-left-style: solid;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #1DB954;
                color: white;
            }
            QLineEdit[echoMode="4"] {  /* Password mode for the auth token */
                background-color: #282828;
                color: #FFFFFF;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 6px;
            }
            QLineEdit, QComboBox {
                padding: 8px 10px;
            }
            QCheckBox {
                padding: 4px 0px;
            }
        """)
        
        
        self.init_ui()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        header_layout = QHBoxLayout()
        logo_label = QLabel("Spotify Downloader Pro")
        logo_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        logo_label.setStyleSheet("color: #1DB954;")
        header_layout.addWidget(logo_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        # tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # tabs
        self.create_download_tab()
        self.create_settings_tab()
        self.create_history_tab()
        self.create_about_tab()
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)
        self.statusBar().setStyleSheet("background-color: #282828; color: #BBBBBB;")
        
    def clean_spotify_url(self, url):
        if not url:
            return url
        # Strip whitespace
        url = url.strip()
        # Remove everything after ?
        if '?' in url:
            url = url.split('?')[0]
        # Remove everything after #
        if '#' in url:
            url = url.split('#')[0]
        return url
    
    def on_url_edited(self):
        current_text = self.url_entry.text()
        cleaned = self.clean_spotify_url(current_text)
        # Only update if actually changed
        if cleaned != current_text:
            self.url_entry.setText(cleaned)

    def create_download_tab(self):
        download_tab = QWidget()
        layout = QVBoxLayout(download_tab)
        layout.setSpacing(15)
        
        # URL input
        url_group = QGroupBox("Download Source")
        url_layout = QVBoxLayout(url_group)
        
        url_input_layout = QHBoxLayout()
        url_label = QLabel("Spotify URL:")
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Enter Spotify track, album, playlist or artist URL")
        self.url_entry.editingFinished.connect(self.on_url_edited)
        url_input_layout.addWidget(url_label)
        url_input_layout.addWidget(self.url_entry)
        url_layout.addLayout(url_input_layout)
        
        quick_buttons_layout = QHBoxLayout()
        self.liked_songs_btn = QPushButton("Download Liked Songs")
        self.liked_songs_btn.clicked.connect(lambda: self.url_entry.setText("saved"))
        self.custom_url_btn = QPushButton("Download from URL")
        self.custom_url_btn.clicked.connect(self.start_download)
        quick_buttons_layout.addWidget(self.liked_songs_btn)
        quick_buttons_layout.addWidget(self.custom_url_btn)
        url_layout.addLayout(quick_buttons_layout)
        
        layout.addWidget(url_group)
        
        # Set Download location
        location_group = QGroupBox("Download Location")
        location_layout = QHBoxLayout(location_group)
        
        location_label = QLabel("Save to:")
        self.download_location_entry = QLineEdit()
        self.download_location_entry.setReadOnly(True)
        self.download_location_entry.setText(self.settings.get("download_location", os.path.expanduser("~/Music")))
        
        download_browse_btn = QPushButton("Browse")
        download_browse_btn.clicked.connect(self.browse_download_location)
        
        location_layout.addWidget(location_label)
        location_layout.addWidget(self.download_location_entry)
        location_layout.addWidget(download_browse_btn)
        
        layout.addWidget(location_group)
        
        # Download options
        options_group = QGroupBox("Download Options")
        options_layout = QVBoxLayout(options_group)
        options_layout.setSpacing(12)
        options_layout.setContentsMargins(12, 20, 12, 12)

        # Format row
        format_layout = QHBoxLayout()
        format_layout.setSpacing(10)
        format_label = QLabel("Format:")
        format_label.setFixedWidth(90)
        format_layout.addWidget(format_label)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp3", "flac", "ogg", "m4a", "opus", "wav"])
        self.format_combo.setMinimumHeight(32)
        format_layout.addWidget(self.format_combo)
        options_layout.addLayout(format_layout)

        # Quality row
        quality_layout = QHBoxLayout()
        quality_layout.setSpacing(10)
        quality_label = QLabel("Quality:")
        quality_label.setFixedWidth(90)
        quality_layout.addWidget(quality_label)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["128k", "192k", "256k", "320k"])
        self.quality_combo.setCurrentText("320k")
        self.quality_combo.setMinimumHeight(32)
        quality_layout.addWidget(self.quality_combo)
        options_layout.addLayout(quality_layout)

        # Auth checkbox row
        auth_layout = QHBoxLayout()
        auth_layout.setContentsMargins(0, 4, 0, 4)
        self.auth_checkbox = QCheckBox("Use Spotify Authentication")
        self.auth_checkbox.setChecked(True)
        self.auth_checkbox.setMinimumHeight(28)
        auth_layout.addWidget(self.auth_checkbox)
        auth_layout.addStretch()
        options_layout.addLayout(auth_layout)

        # Token row
        token_layout = QHBoxLayout()
        token_layout.setSpacing(10)
        token_label = QLabel("Access Token:")
        token_label.setFixedWidth(90)
        token_layout.addWidget(token_label)
        self.auth_token_entry = QLineEdit()
        self.auth_token_entry.setPlaceholderText("Paste your Spotify access token here (optional)")
        self.auth_token_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.auth_token_entry.setToolTip("Optional: Provide a Spotify access token for non premium users")
        self.auth_token_entry.setMinimumHeight(32)
        token_layout.addWidget(self.auth_token_entry)
        options_layout.addLayout(token_layout)

        layout.addWidget(options_group)
        
        # Progress section
        progress_group = QGroupBox("Download Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setFont(QFont("Consolas", 10))
        self.console_text.setMinimumHeight(200)
        progress_layout.addWidget(self.console_text)
        
        layout.addWidget(progress_group)
        self.tab_widget.addTab(download_tab, "Download")
        
    def create_settings_tab(self):
        settings_tab = QWidget()
        layout = QVBoxLayout(settings_tab)
        
        # Download location
        location_group = QGroupBox("Download Location")
        location_layout = QHBoxLayout(location_group)
        
        self.location_entry = QLineEdit()
        self.location_entry.setReadOnly(True)
        self.location_entry.setText(self.settings.get("download_location", os.path.expanduser("~/Music")))
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_location)
        
        location_layout.addWidget(self.location_entry)
        location_layout.addWidget(browse_btn)
        
        layout.addWidget(location_group)
        
        # Appearance settings
        # Not yet fully implemented...
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout(appearance_group)
        
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        theme_combo = QComboBox()
        theme_combo.addItems(["Dark (Default)", "Light", "System"])
        theme_layout.addWidget(theme_combo)
        
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("Console Font Size:"))
        font_size_spin = QSpinBox()
        font_size_spin.setRange(8, 16)
        font_size_spin.setValue(10)
        font_size_spin.valueChanged.connect(lambda v: self.console_text.setFont(QFont("Consolas", v)))
        font_size_layout.addWidget(font_size_spin)
        
        appearance_layout.addLayout(theme_layout)
        appearance_layout.addLayout(font_size_layout)
        
        layout.addWidget(appearance_group)
        
        # Advanced settings
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QVBoxLayout(advanced_group)
        
        concurrent_layout = QHBoxLayout()
        concurrent_layout.addWidget(QLabel("Concurrent Downloads:"))
        concurrent_spin = QSpinBox()
        concurrent_spin.setRange(1, 5)
        concurrent_spin.setValue(1)
        concurrent_layout.addWidget(concurrent_spin)
        
        metadata_checkbox = QCheckBox("Embed Metadata")
        metadata_checkbox.setChecked(True)
        
        artwork_checkbox = QCheckBox("Download Album Artwork")
        artwork_checkbox.setChecked(True)
        
        advanced_layout.addLayout(concurrent_layout)
        advanced_layout.addWidget(metadata_checkbox)
        advanced_layout.addWidget(artwork_checkbox)
        
        layout.addWidget(advanced_group)
        layout.addStretch()
    
        self.tab_widget.addTab(settings_tab, "Settings")
        
    def create_history_tab(self):
        history_tab = QWidget()
        layout = QVBoxLayout(history_tab)
        
        # Recent downloads
        history_label = QLabel("Recent Downloads")
        history_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(history_label)
        
        # History list
        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        layout.addWidget(self.history_list)
        self.update_history_display()
        
        # Clear history button
        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(self.clear_history)
        layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.tab_widget.addTab(history_tab, "History")
        
    def create_about_tab(self):
        about_tab = QWidget()
        layout = QVBoxLayout(about_tab)
        
        # App info
        about_label = QLabel("Spotify Downloader Pro")
        about_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        about_label.setStyleSheet("color: #1DB954;")
        about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        version_label = QLabel("Version 1.6.4 BETA")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        description = QLabel(
            "A professional tool to download music from Spotify.\n"
            "This application uses spotDL to download high-quality music from Spotify."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        
        # Links
        github_btn = QPushButton("GitHub Repository")
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/OmiiiDev/SpotifyDL")))
        
        donate_btn = QPushButton("Join us on Discord!")
        donate_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://discord.gg/B7apjZHRAd")))
        # Credits
        credits_label = QLabel("Powered by spotDL")
        credits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(about_label)
        layout.addWidget(version_label)
        layout.addSpacing(20)
        layout.addWidget(description)
        layout.addSpacing(20)
        layout.addWidget(github_btn)
        layout.addWidget(donate_btn)
        layout.addSpacing(20)
        layout.addWidget(credits_label)
        layout.addStretch()
        
        # Add tab
        self.tab_widget.addTab(about_tab, "About")
        
    def browse_download_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.download_location_entry.text())
        if folder:
            self.download_location_entry.setText(folder)
            self.location_entry.setText(folder)  # Sync with settings tab
            self.save_settings()

    def browse_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.location_entry.text())
        if folder:
            self.location_entry.setText(folder)
            self.download_location_entry.setText(folder)  # Sync with download tab
            self.save_settings()
            
    def start_download(self):
        url = self.url_entry.text()
        url = self.clean_spotify_url(self.url_entry.text())
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a Spotify URL.")
            return
            
        download_path = self.download_location_entry.text()
        if not os.path.exists(download_path):
            try:
                os.makedirs(download_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create download directory: {str(e)}")
                return
                
        # Clear console and reset progress
        self.console_text.clear()
        self.progress_bar.setValue(0)
        self.update_status("Downloading...")
        
        # Get settings
        quality = self.quality_combo.currentText()
        format_type = self.format_combo.currentText()
        use_auth = self.auth_checkbox.isChecked()
        auth_token = self.auth_token_entry.text()
        
        # Start download in a separate thread
        self.download_thread = DownloadWorker(url, download_path, quality, format_type, use_auth, auth_token)
        self.download_thread.update_console.connect(self.update_console)
        self.download_thread.update_progress.connect(self.update_progress)
        self.download_thread.download_complete.connect(self.download_finished)
        self.download_thread.start()
        
    def update_console(self, text):
        self.console_text.append(text)
        # Auto-scroll to bottom
        scrollbar = self.console_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def update_progress(self, current, total):
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)
        self.update_status(f"Downloading {current}/{total}")
        
    def update_status(self, text):
        self.status_label.setText(text)

    # needs fixing  
    def download_finished(self, success, message, content, timestamp):
        if success:
            self.update_status("Download completed successfully!")
            QMessageBox.information(self, "Download Complete", "Song(s) downloaded successfully!")
            
            # Add to history
            history_entry = {
                "timestamp": timestamp,
                "content": content,
                "status": "Success",
                "format": self.format_combo.currentText(),
                "quality": self.quality_combo.currentText(),
                "path": self.download_location_entry.text()
            }
            self.add_to_history(history_entry)
            
        else:
            self.update_status("Download failed.")
            QMessageBox.critical(self, "Download Error", f"An error occurred while downloading: {message}")
            
            # Add failed download to history
            history_entry = {
                "timestamp": timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "content": content or self.url_entry.text(),
                "status": "Failed",
                "error": message,
                "format": self.format_combo.currentText(),
                "quality": self.quality_combo.currentText()
            }
            self.add_to_history(history_entry)
            
        self.progress_bar.setValue(100)
        
    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading history: {e}")
                return []
        return []
        
    def save_history(self):
        try:
            # Ensure directory exists
            if not os.path.exists(self.app_data_dir):
                os.makedirs(self.app_data_dir)
            
            with open(self.history_file, 'w') as f:
                json.dump(self.download_history, f, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")
            self.update_console(f"Error saving history: {e}")
            
    def add_to_history(self, entry):
        self.download_history.insert(0, entry)  # Add to beginning of list
        # Limit history to 100 entries
        if len(self.download_history) > 100:
            self.download_history = self.download_history[:100]
        self.save_history()
        self.update_history_display()
        
    def update_history_display(self):
        self.history_list.clear()
        for entry in self.download_history:
            timestamp = entry.get("timestamp", "Unknown")
            content = entry.get("content", "Unknown")
            status = entry.get("status", "Unknown")
            quality = entry.get("quality", "")
            format_type = entry.get("format", "")
            
            # Create formatted item text
            if status == "Success":
                item_text = f"✅ {timestamp} - {content} ({quality}, {format_type})"
            else:
                error = entry.get("error", "Unknown error")
                item_text = f"❌ {timestamp} - {content} - Error: {error}"
                
            item = QListWidgetItem(item_text)
            self.history_list.addItem(item)
            
    def clear_history(self):
        reply = QMessageBox.question(self, "Clear History", 
                                     "Are you sure you want to clear your download history?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.download_history = []
            self.save_history()
            self.update_history_display()

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading settings: {e}")
                return {"download_location": os.path.expanduser("~/Music")}
        return {"download_location": os.path.expanduser("~/Music")}

    def save_settings(self):
        try:
            # Ensure directory exists
            if not os.path.exists(self.app_data_dir):
                os.makedirs(self.app_data_dir)
            
            self.settings["download_location"] = self.download_location_entry.text()
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
            self.update_console(f"Error saving settings: {e}")


class LoadingDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Checking for Updates")
        self.setFixedSize(400, 120)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.label = QLabel("Checking for spotDL updates...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Arial", 12))
        layout.addWidget(self.label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
        
        # Enhanced style for modern look
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;
                color: #FFFFFF;
                border-radius: 10px;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }
            QProgressBar {
                background-color: #282828;
                border: none;
                border-radius: 2px;
                height: 4px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                  stop:0 #1DB954, stop:1 #1ED760);
                border-radius: 2px;
            }
        """)


class UpdateWorker(QThread):
    update_status = pyqtSignal(str)
    update_progress = pyqtSignal(int)
    start_progress = pyqtSignal()
    finished = pyqtSignal()

    def run(self):
        try:
            # Find spotdl.exe path
            spotdl_dir = os.path.abspath(os.path.dirname(__file__))
            spotdl_path = os.path.join(spotdl_dir, 'spotdl.exe')
            
            if not os.path.exists(spotdl_path):
                self.finished.emit()
                return
            
            # Get current version
            output = subprocess.check_output([spotdl_path, "--version"]).decode().strip()
            current_version = output.split()[-1]  # always take last token

            
            # Get latest release info
            req = urllib.request.Request("https://api.github.com/repos/spotdl/spotify-downloader/releases/latest")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
            
            latest_tag = data['tag_name'].lstrip('v')
            
            def version_tuple(v):
                return tuple(map(int, v.split('.')))
            
            if version_tuple(latest_tag) > version_tuple(current_version):
                self.update_status.emit("Downloading spotDL update...")
                
                # Determine architecture
                asset_name = f"spotdl-{latest_tag}-win32.exe"
                
                # Find the asset
                download_url = None
                for asset in data['assets']:
                    if asset['name'] == asset_name:
                        download_url = asset['browser_download_url']
                        break
                
                if download_url:
                    self.start_progress.emit()
                    req = urllib.request.Request(download_url)
                    with urllib.request.urlopen(req) as response:
                        total_size = int(response.headers.get('Content-Length', 0))
                        block_size = 1024
                        downloaded = 0
                        temp_path = spotdl_path + '.new'
                        with open(temp_path, 'wb') as file:
                            while True:
                                chunk = response.read(block_size)
                                if not chunk:
                                    break
                                file.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    progress = int((downloaded / total_size) * 100)
                                    self.update_progress.emit(progress)
                    
                    os.remove(spotdl_path)
                    os.rename(temp_path, spotdl_path)
        except Exception as e:
            # Silently fail
            pass
        
        self.finished.emit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    loading = LoadingDialog()
    loading.show()
    
    worker = UpdateWorker()
    worker.update_status.connect(loading.label.setText)
    worker.update_progress.connect(loading.progress_bar.setValue)
    worker.start_progress.connect(lambda: loading.progress_bar.setMaximum(100))
    
    def on_finished():
        loading.close()
        window = SpotifyDownloaderApp()
        window.show()
    
    worker.finished.connect(on_finished)
    worker.start()
    
    sys.exit(app.exec())
