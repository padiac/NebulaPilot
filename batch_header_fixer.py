import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QFileDialog, QListWidget, QTextEdit, 
    QProgressBar, QFrame, QMessageBox, QLineEdit
)
from PySide6.QtCore import Qt, QThread, Signal
from astropy.io import fits

# Dark Theme Stylesheet (Reused for consistency)
DARK_THEME = """
QMainWindow, QDialog, QMessageBox { background-color: #1e1e1e; color: #e0e0e0; }
QWidget { font-family: "Segoe UI", sans-serif; font-size: 14px; color: #e0e0e0; }
QPushButton { background-color: #007acc; color: white; border: none; padding: 8px 16px; border-radius: 4px; }
QPushButton:hover { background-color: #005f9e; }
QPushButton:disabled { background-color: #3e3e42; color: #888888; }
QListWidget, QTextEdit { background-color: #252526; border: 1px solid #3e3e42; border-radius: 4px; color: #e0e0e0; }
QProgressBar { background-color: #3e3e42; border: none; border-radius: 4px; text-align: center; color: white; }
QProgressBar::chunk { background-color: #007acc; border-radius: 4px; }
QLabel { color: #e0e0e0; }
"""

class Worker(QThread):
    progress = Signal(str)
    finished = Signal()

    def __init__(self, folders, correct_target):
        super().__init__()
        self.folders = folders
        self.correct_target = correct_target
        self.running = True

    def run(self):
        total_files = 0
        fits_files = []
        
        # 1. Scan for files
        self.progress.emit("Scanning folders for FITS files...")
        for folder in self.folders:
            p = Path(folder)
            for ext in ["*.fits", "*.fit", "*.fts"]:
                fits_files.extend(list(p.rglob(ext)))
        
        total = len(fits_files)
        self.progress.emit(f"Found {total} files. Starting update...")
        
        count = 0
        success = 0
        failed = 0
        
        for f in fits_files:
            if not self.running:
                break
            
            try:
                with fits.open(f, mode='update') as hdul:
                    # Update OBJECT header
                    old_obj = hdul[0].header.get('OBJECT', 'Unknown')
                    hdul[0].header['OBJECT'] = self.correct_target
                    hdul.flush()
                    success += 1
                    # self.progress.emit(f"Fixed: {f.name} ({old_obj} -> {self.correct_target})")
            except Exception as e:
                failed += 1
                self.progress.emit(f"ERROR: {f.name} - {str(e)}")
            
            count += 1
            if count % 10 == 0:
                self.progress.emit(f"Progress: {count}/{total}")

        self.progress.emit(f"\nDONE! Updated {success} files. Failed: {failed}.")
        self.finished.emit()

    def stop(self):
        self.running = False

class DropListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # DropOnly is fine, but we override events anyway
        self.setDragDropMode(QListWidget.DropOnly)
        self.setSelectionMode(QListWidget.ExtendedSelection) # Allow selecting multiple items in the list itself too
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept() # Accept everything with URLs
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction) # Force CopyAction visual
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            added_count = 0
            for url in md.urls():
                # toLocalFile returns path. For Windows it handles the /C:/ format.
                path = url.toLocalFile()
                
                # Verify it is a directory
                if os.path.isdir(path):
                    # Find main window instance to update data
                    parent = self.window()
                    if hasattr(parent, 'add_folder_path'):
                        parent.add_folder_path(path)
                        added_count += 1
            
            if added_count > 0:
                event.accept()

class BatchHeaderFixer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Batch Header Fixer - NebulaPilot Tool")
        self.resize(800, 600)
        self.setStyleSheet(DARK_THEME)
        
        self.ref_target = None
        self.target_folders = []
        
        # Main Layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. Target Name Source
        ref_group = QFrame()
        ref_layout = QVBoxLayout(ref_group)
        
        ref_header = QLabel("1. Define Target Name")
        ref_header.setStyleSheet("font-weight: bold; font-size: 16px; color: #ffffff;")
        ref_layout.addWidget(ref_header)
        
        # Tabs or Radio structure for File vs Manual
        source_layout = QHBoxLayout()
        
        # Option A: From File
        self.btn_ref = QPushButton("Load from File...")
        self.btn_ref.setCursor(Qt.PointingHandCursor)
        self.btn_ref.clicked.connect(self.select_reference)
        
        # Option B: Manual
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("Or type Target Name manually (e.g., M42)")
        self.manual_input.textChanged.connect(self.on_manual_input)
        
        source_layout.addWidget(self.btn_ref)
        source_layout.addWidget(QLabel(" OR "))
        source_layout.addWidget(self.manual_input)
        
        ref_layout.addLayout(source_layout)
        
        self.lbl_ref = QLabel("Current Target to Apply: [None]")
        self.lbl_ref.setStyleSheet("color: #ebbcba; font-weight: bold; font-size: 14px; margin-top: 5px;")
        self.lbl_ref.setAlignment(Qt.AlignCenter)
        ref_layout.addWidget(self.lbl_ref)
        
        layout.addWidget(ref_group)
        
        # 2. Folders Section
        folder_group = QFrame()
        folder_layout = QVBoxLayout(folder_group)
        
        folder_header = QLabel("2. Select Target Folders (Files to Modify)")
        folder_header.setStyleSheet("font-weight: bold; font-size: 16px; color: #ffffff;")
        folder_layout.addWidget(folder_header)
        
        folder_btn_layout = QHBoxLayout()
        self.btn_add_folder = QPushButton("Add Folder")
        self.btn_add_folder.setCursor(Qt.PointingHandCursor)
        self.btn_add_folder.clicked.connect(self.add_folder)
        
        self.btn_clear_folders = QPushButton("Clear List")
        self.btn_clear_folders.setCursor(Qt.PointingHandCursor)
        self.btn_clear_folders.setStyleSheet("background-color: #d32f2f;")
        self.btn_clear_folders.clicked.connect(self.clear_folders)
        
        folder_btn_layout.addWidget(self.btn_add_folder)
        folder_btn_layout.addWidget(self.btn_clear_folders)
        folder_btn_layout.addStretch()
        folder_layout.addLayout(folder_btn_layout)
        
        self.list_folders = DropListWidget()
        self.list_folders.setFixedHeight(150)
        folder_layout.addWidget(self.list_folders)
        
        # Add label explaining drag & drop
        hint_label = QLabel("Tip: You can drag and drop multiple folders here.")
        hint_label.setStyleSheet("color: #888888; font-style: italic; font-size: 12px;")
        folder_layout.addWidget(hint_label)
        
        layout.addWidget(folder_group)
        
        # 3. Action Section
        self.btn_run = QPushButton("APPLY FIX TO ALL FILES")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.setFixedHeight(50)
        self.btn_run.setStyleSheet("background-color: #2e7d32; font-size: 16px; font-weight: bold;")
        self.btn_run.clicked.connect(self.run_fix)
        self.btn_run.setEnabled(False)
        layout.addWidget(self.btn_run)
        
        # 4. Logs
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)
        
        self.log("Welcome. Select a reference file to begin.")

    def log(self, message):
        self.log_box.append(message)
        # Auto scroll
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def select_reference(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Reference FITS", "", "FITS Files (*.fits *.fit *.fts)")
        if file_path:
            try:
                with fits.open(file_path) as hdul:
                    target_name = hdul[0].header.get("OBJECT")
                
                if target_name:
                    self.manual_input.setText(target_name)
                    self.log(f"Loaded target '{target_name}' from file: {Path(file_path).name}")
                else:
                    self.log("Error: No OBJECT header found in that file.")
            except Exception as e:
                self.log(f"Error reading file: {e}")

    def on_manual_input(self, text):
        self.ref_target = text.strip()
        if self.ref_target:
            self.lbl_ref.setText(f"Target to Apply: '{self.ref_target}'")
            self.lbl_ref.setStyleSheet("color: #98c379; font-weight: bold; font-size: 14px; margin-top: 5px;")
        else:
            self.lbl_ref.setText("Current Target to Apply: [None]")
            self.lbl_ref.setStyleSheet("color: #ebbcba; font-weight: bold; font-size: 14px; margin-top: 5px;")
        self.check_ready()
                
    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing FITS Files")
        if folder:
            self.add_folder_path(folder)

    def add_folder_path(self, folder):
        if folder not in self.target_folders:
            self.target_folders.append(folder)
            self.list_folders.addItem(folder)
            self.log(f"Added folder: {folder}")
            self.check_ready()
    
    def clear_folders(self):
        self.target_folders = []
        self.list_folders.clear()
        self.check_ready()
        self.log("Cleared folder list.")

    def check_ready(self):
        is_ready = (self.ref_target is not None) and (len(self.target_folders) > 0)
        self.btn_run.setEnabled(is_ready)

    def run_fix(self):
        confirm = QMessageBox.question(
            self, "Confirm Batch Fix",
            f"Are you sure you want to update FITS files in {len(self.target_folders)} folders?\n\n"
            f"Target Name will be set to: '{self.ref_target}'\n\n"
            "This will MODIFY your files on disk.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.btn_run.setEnabled(False)
            self.btn_add_folder.setEnabled(False)
            self.btn_clear_folders.setEnabled(False)
            self.btn_ref.setEnabled(False)
            
            self.worker = Worker(self.target_folders, self.ref_target)
            self.worker.progress.connect(self.log)
            self.worker.finished.connect(self.on_finished)
            self.worker.start()
            
    def on_finished(self):
        self.btn_run.setEnabled(True)
        self.btn_add_folder.setEnabled(True)
        self.btn_clear_folders.setEnabled(True)
        self.btn_ref.setEnabled(True)
        QMessageBox.information(self, "Complete", "Batch update finished. Check logs for details.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BatchHeaderFixer()
    window.show()
    sys.exit(app.exec())
