import sys
import os
import threading
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                            QTextEdit, QFileDialog, QListWidget, QListWidgetItem,
                            QMessageBox, QTabWidget, QGridLayout, QGroupBox,
                            QFormLayout, QComboBox, QCheckBox, QProgressBar,
                            QSplitter, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QFont, QColor

# Add parent directory to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from client import FileClient
from server.encryption import FileEncryptor

class UploadWorker(QThread):
    """Worker thread for uploading files"""
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, client, file_path):
        super().__init__()
        self.client = client
        self.file_path = file_path
    
    def run(self):
        self.progress_signal.emit(f"Uploading {os.path.basename(self.file_path)}...")
        success = self.client.upload_file(self.file_path)
        
        if success:
            self.finished_signal.emit(True, f"Successfully uploaded {os.path.basename(self.file_path)}")
        else:
            self.finished_signal.emit(False, f"Failed to upload {os.path.basename(self.file_path)}")

class DownloadWorker(QThread):
    """Worker thread for downloading files"""
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, client, file_id, filename):
        super().__init__()
        self.client = client
        self.file_id = file_id
        self.filename = filename
    
    def run(self):
        self.progress_signal.emit(f"Downloading {self.filename}...")
        success = self.client.download_file(self.file_id, output_path=os.path.join(self.client.download_dir, self.filename))
        
        if success:
            self.finished_signal.emit(True, f"Successfully downloaded {self.filename}")
        else:
            self.finished_signal.emit(False, f"Failed to download {self.filename}")

class ListFilesWorker(QThread):
    """Worker thread for listing files"""
    finished_signal = pyqtSignal(list)
    
    def __init__(self, client):
        super().__init__()
        self.client = client
    
    def run(self):
        files = self.client.list_files()
        self.finished_signal.emit(files)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.client = FileClient()
        
        self.setWindowTitle("Secure File Transfer")
        self.setMinimumSize(800, 600)
        
        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Create connection section
        connection_group = QGroupBox("Server Connection")
        connection_layout = QHBoxLayout()
        
        self.host_input = QLineEdit("localhost")
        self.port_input = QLineEdit("5000")
        self.port_input.setMaximumWidth(100)
        self.connect_button = QPushButton("Connect")
        self.connect_status = QLabel("Not Connected")
        self.connect_status.setStyleSheet("color: red")
        
        connection_layout.addWidget(QLabel("Host:"))
        connection_layout.addWidget(self.host_input)
        connection_layout.addWidget(QLabel("Port:"))
        connection_layout.addWidget(self.port_input)
        connection_layout.addWidget(self.connect_button)
        connection_layout.addWidget(self.connect_status)
        connection_layout.addStretch()
        
        connection_group.setLayout(connection_layout)
        main_layout.addWidget(connection_group)
        
        # Create tab widget for different functions
        self.tabs = QTabWidget()
        
        # Create upload tab
        upload_widget = QWidget()
        upload_layout = QVBoxLayout(upload_widget)
        
        upload_file_layout = QHBoxLayout()
        self.upload_path_input = QLineEdit()
        self.upload_path_input.setPlaceholderText("Select a file to upload")
        self.upload_browse_button = QPushButton("Browse")
        self.upload_button = QPushButton("Upload")
        self.upload_button.setEnabled(False)
        
        upload_file_layout.addWidget(self.upload_path_input)
        upload_file_layout.addWidget(self.upload_browse_button)
        upload_file_layout.addWidget(self.upload_button)
        
        upload_layout.addLayout(upload_file_layout)
        
        self.upload_log = QTextEdit()
        self.upload_log.setReadOnly(True)
        upload_layout.addWidget(QLabel("Upload Log:"))
        upload_layout.addWidget(self.upload_log)
        
        self.tabs.addTab(upload_widget, "Upload")
        
        # Create download tab
        download_widget = QWidget()
        download_layout = QVBoxLayout(download_widget)
        
        self.refresh_button = QPushButton("Refresh File List")
        download_layout.addWidget(self.refresh_button)
        
        self.file_list = QListWidget()
        download_layout.addWidget(QLabel("Available Files:"))
        download_layout.addWidget(self.file_list)
        
        self.download_button = QPushButton("Download Selected")
        self.download_button.setEnabled(False)
        download_layout.addWidget(self.download_button)
        
        self.download_log = QTextEdit()
        self.download_log.setReadOnly(True)
        download_layout.addWidget(QLabel("Download Log:"))
        download_layout.addWidget(self.download_log)
        
        self.tabs.addTab(download_widget, "Download")
        
        # Create encryption keys tab
        keys_widget = QWidget()
        keys_layout = QVBoxLayout(keys_widget)
        
        keys_actions_layout = QHBoxLayout()
        self.save_keys_button = QPushButton("Save Keys")
        self.load_keys_button = QPushButton("Load Keys")
        keys_actions_layout.addWidget(self.save_keys_button)
        keys_actions_layout.addWidget(self.load_keys_button)
        keys_actions_layout.addStretch()
        
        keys_layout.addLayout(keys_actions_layout)
        
        self.keys_text = QTextEdit()
        self.keys_text.setReadOnly(True)
        keys_layout.addWidget(QLabel("Saved Encryption Keys:"))
        keys_layout.addWidget(self.keys_text)
        
        self.tabs.addTab(keys_widget, "Encryption Keys")
        
        main_layout.addWidget(self.tabs)
        
        # Create status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Set main widget
        self.setCentralWidget(main_widget)
        
        # Connect signals and slots
        self.connect_button.clicked.connect(self.toggle_connection)
        self.upload_browse_button.clicked.connect(self.browse_upload_file)
        self.upload_button.clicked.connect(self.upload_file)
        self.refresh_button.clicked.connect(self.refresh_file_list)
        self.file_list.itemClicked.connect(self.enable_download_button)
        self.download_button.clicked.connect(self.download_file)
        self.save_keys_button.clicked.connect(self.save_keys)
        self.load_keys_button.clicked.connect(self.load_keys)
        self.upload_path_input.textChanged.connect(self.check_upload_path)
        
        # Initialize
        self.update_keys_display()
    
    def toggle_connection(self):
        """Connect to or disconnect from the server"""
        if not self.client.connected:
            host = self.host_input.text().strip()
            try:
                port = int(self.port_input.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Invalid Port", "Please enter a valid port number.")
                return
            
            self.client.host = host
            self.client.port = port
            
            if self.client.connect():
                self.connect_status.setText("Connected")
                self.connect_status.setStyleSheet("color: green")
                self.connect_button.setText("Disconnect")
                self.status_bar.showMessage(f"Connected to {host}:{port}")
                
                # Load the file list
                self.refresh_file_list()
            else:
                QMessageBox.warning(self, "Connection Failed", f"Failed to connect to {host}:{port}")
        else:
            self.client.disconnect()
            self.connect_status.setText("Not Connected")
            self.connect_status.setStyleSheet("color: red")
            self.connect_button.setText("Connect")
            self.status_bar.showMessage("Disconnected")
    
    def browse_upload_file(self):
        """Open file dialog to select a file to upload"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if file_path:
            self.upload_path_input.setText(file_path)
    
    def check_upload_path(self):
        """Enable or disable upload button based on path input"""
        self.upload_button.setEnabled(bool(self.upload_path_input.text().strip()))
    
    def upload_file(self):
        """Upload the selected file to the server"""
        if not self.client.connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to the server first.")
            return
        
        file_path = self.upload_path_input.text().strip()
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found", f"The file {file_path} does not exist.")
            return
        
        # Create and start worker thread
        self.upload_worker = UploadWorker(self.client, file_path)
        self.upload_worker.progress_signal.connect(self.update_upload_log)
        self.upload_worker.finished_signal.connect(self.upload_finished)
        
        # Disable upload button while uploading
        self.upload_button.setEnabled(False)
        self.upload_button.setText("Uploading...")
        
        # Start the worker thread
        self.upload_worker.start()
    
    def update_upload_log(self, message):
        """Update the upload log with a new message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.upload_log.append(f"[{timestamp}] {message}")
    
    def upload_finished(self, success, message):
        """Handle upload completion"""
        self.update_upload_log(message)
        
        # Re-enable upload button
        self.upload_button.setEnabled(True)
        self.upload_button.setText("Upload")
        
        if success:
            # Refresh file list
            self.refresh_file_list()
            # Update keys display
            self.update_keys_display()
    
    def refresh_file_list(self):
        """Refresh the list of files from the server"""
        if not self.client.connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to the server first.")
            return
        
        # Clear the list
        self.file_list.clear()
        
        # Create and start worker thread
        self.list_worker = ListFilesWorker(self.client)
        self.list_worker.finished_signal.connect(self.update_file_list)
        
        # Update status
        self.status_bar.showMessage("Refreshing file list...")
        
        # Start the worker thread
        self.list_worker.start()
    
    def update_file_list(self, files):
        """Update the file list with files from the server"""
        for file_info in files:
            file_id = file_info.get('id')
            file_name = file_info.get('name')
            created_time = file_info.get('createdTime', '')
            
            # Create item with file info
            item = QListWidgetItem(f"{file_name} (ID: {file_id})")
            item.setData(Qt.UserRole, file_id)  # Store file ID for download
            item.setToolTip(f"Created: {created_time}")
            
            self.file_list.addItem(item)
        
        self.status_bar.showMessage(f"Found {len(files)} files")
    
    def enable_download_button(self, item):
        """Enable the download button when a file is selected"""
        self.download_button.setEnabled(True)
    
    def download_file(self):
        """Download the selected file from the server"""
        if not self.client.connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to the server first.")
            return
        
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return
        
        selected_item = selected_items[0]
        file_id = selected_item.data(Qt.UserRole)
        filename = selected_item.text().split(" (ID:")[0]
        
        # Get the original filename without the .enc extension if present
        original_filename = filename[:-4] if filename.endswith('.enc') else filename
        
        # Create and start worker thread
        self.download_worker = DownloadWorker(self.client, file_id, original_filename)
        self.download_worker.progress_signal.connect(self.update_download_log)
        self.download_worker.finished_signal.connect(self.download_finished)
        
        # Disable download button while downloading
        self.download_button.setEnabled(False)
        self.download_button.setText("Downloading...")
        
        # Start the worker thread
        self.download_worker.start()
    
    def update_download_log(self, message):
        """Update the download log with a new message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.download_log.append(f"[{timestamp}] {message}")
    
    def download_finished(self, success, message):
        """Handle download completion"""
        self.update_download_log(message)
        
        # Re-enable download button
        self.download_button.setEnabled(True)
        self.download_button.setText("Download Selected")
    
    def save_keys(self):
        """Save encryption keys to a file"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Encryption Keys", "file_keys.json", "JSON Files (*.json)")
        if file_path:
            success = self.client.save_keys_to_file(file_path)
            if success:
                QMessageBox.information(self, "Keys Saved", f"Encryption keys saved to {file_path}")
            else:
                QMessageBox.warning(self, "Save Failed", "Failed to save encryption keys")
    
    def load_keys(self):
        """Load encryption keys from a file"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Encryption Keys", "", "JSON Files (*.json)")
        if file_path:
            success = self.client.load_keys_from_file(file_path)
            if success:
                QMessageBox.information(self, "Keys Loaded", f"Encryption keys loaded from {file_path}")
                self.update_keys_display()
            else:
                QMessageBox.warning(self, "Load Failed", "Failed to load encryption keys")
    
    def update_keys_display(self):
        """Update the display of saved encryption keys"""
        self.keys_text.clear()
        
        if not self.client.saved_keys:
            self.keys_text.setText("No encryption keys saved")
            return
        
        for file_id, key in self.client.saved_keys.items():
            self.keys_text.append(f"File ID: {file_id}")
            self.keys_text.append(f"Key: {key}")
            self.keys_text.append("")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 