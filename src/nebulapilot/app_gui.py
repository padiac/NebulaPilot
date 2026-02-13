import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QPushButton, QProgressBar, 
    QLabel, QFileDialog, QHeaderView, QLineEdit, QDialog, QFormLayout
)
from PySide6.QtCore import Qt, QTimer
from .db import init_db, get_targets, update_target_goals, get_target_progress
from .scanner import scan_directory
from .organizer import organize_directory
from PySide6.QtWidgets import QMessageBox

class GoalDialog(QDialog):
    def __init__(self, target_name, goals, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Set Goals for {target_name}")
        self.layout = QFormLayout(self)
        
        self.l_input = QLineEdit(str(goals[0]))
        self.r_input = QLineEdit(str(goals[1]))
        self.g_input = QLineEdit(str(goals[2]))
        self.b_input = QLineEdit(str(goals[3]))
        
        self.layout.addRow("L Goal (min):", self.l_input)
        self.layout.addRow("R Goal (min):", self.r_input)
        self.layout.addRow("G Goal (min):", self.g_input)
        self.layout.addRow("B Goal (min):", self.b_input)
        
        self.buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.buttons.addWidget(self.save_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addRow(self.buttons)

    def get_values(self):
        try:
            return (
                float(self.l_input.text()),
                float(self.r_input.text()),
                float(self.g_input.text()),
                float(self.b_input.text())
            )
        except ValueError:
            return None

class NebulaPilotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("nebulaPilot - Astrophotography Progress Tracker")
        self.resize(1000, 600)
        
        init_db()
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Header
        self.header_layout = QHBoxLayout()
        self.title_label = QLabel("Target Exposure Progress")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        
        self.scan_btn = QPushButton("Scan Directory")
        self.scan_btn.clicked.connect(self.on_scan_clicked)
        self.header_layout.addWidget(self.scan_btn)

        self.organize_btn = QPushButton("Organize Files")
        self.organize_btn.clicked.connect(self.on_organize_clicked)
        self.header_layout.addWidget(self.organize_btn)
        
        self.layout.addLayout(self.header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Target", "Progress L", "Progress R", "Progress G", "Progress B", "Status", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(self.table)
        
        self.refresh_table()
        
    def refresh_table(self):
        targets = get_targets()
        self.table.setRowCount(len(targets))
        
        for i, target in enumerate(targets):
            name = target["name"]
            goals = (target["goal_l"], target["goal_r"], target["goal_g"], target["goal_b"])
            progress = get_target_progress(name)
            
            self.table.setItem(i, 0, QTableWidgetItem(name))
            
            # Progress Bars
            for j, f in enumerate(["L", "R", "G", "B"]):
                goal = goals[j]
                current = progress[f]
                
                container = QWidget()
                vbox = QVBoxLayout(container)
                vbox.setContentsMargins(5, 2, 5, 2)
                
                p_bar = QProgressBar()
                if goal > 0:
                    percent = min(100, int((current / goal) * 100))
                    p_bar.setValue(percent)
                else:
                    p_bar.setValue(0)
                
                label = QLabel(f"{current:.1f} / {goal:.1f} min")
                label.setAlignment(Qt.AlignCenter)
                vbox.addWidget(p_bar)
                vbox.addWidget(label)
                
                self.table.setCellWidget(i, j + 1, container)
            
            self.table.setItem(i, 5, QTableWidgetItem(target["status"]))
            
            # Actions
            edit_btn = QPushButton("Edit Goals")
            edit_btn.clicked.connect(lambda checked, n=name, g=goals: self.on_edit_goals(n, g))
            self.table.setCellWidget(i, 6, edit_btn)

    def on_edit_goals(self, name, goals):
        dialog = GoalDialog(name, goals, self)
        if dialog.exec():
            new_goals = dialog.get_values()
            if new_goals:
                update_target_goals(name, new_goals)
                self.refresh_table()

    def on_scan_clicked(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory to Scan")
        if dir_path:
            scan_directory(dir_path)
            self.refresh_table()

    def on_organize_clicked(self):
        source_dir = QFileDialog.getExistingDirectory(self, "Select Source Directory (Incoming Files)")
        if not source_dir:
            return

        dest_dir = QFileDialog.getExistingDirectory(self, "Select Destination Directory (Organized Storage)")
        if not dest_dir:
            return

        confirm = QMessageBox.question(
            self, 
            "Confirm Organization", 
            f"Are you sure you want to move files from:\n{source_dir}\n\nTo:\n{dest_dir}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            organize_directory(source_dir, dest_dir)
            QMessageBox.information(self, "Success", "File organization complete!")

def main():
    app = QApplication(sys.argv)
    window = NebulaPilotGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
