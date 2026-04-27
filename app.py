import os
import sys

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import database
import plot
from timer_engine import SessionTimer, TimerConfig, format_seconds


BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


class DailyChart(QWidget):
    COLORS = [
        QColor("#2f80ed"),
        QColor("#27ae60"),
        QColor("#f2994a"),
        QColor("#eb5757"),
        QColor("#9b51e0"),
        QColor("#00a7a7"),
        QColor("#6c757d"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.summary = {"days": [], "activities": [], "max_total": 0}
        self.dark_mode = True
        self.setMinimumHeight(230)

    def set_summary(self, summary):
        self.summary = summary
        self.update()

    def set_dark_mode(self, enabled):
        self.dark_mode = enabled
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.dark_mode:
            background_color = QColor("#111827")
            muted_text_color = QColor("#94a3b8")
            label_color = QColor("#e5e7eb")
            value_color = QColor("#cbd5e1")
            legend_color = QColor("#d1d5db")
        else:
            background_color = QColor("#f8fafc")
            muted_text_color = QColor("#5f6b7a")
            label_color = QColor("#334155")
            value_color = QColor("#64748b")
            legend_color = QColor("#475569")

        painter.fillRect(self.rect(), background_color)

        days = self.summary.get("days", [])[-14:]
        activities = self.summary.get("activities", [])
        max_total = self.summary.get("max_total", 0)

        painter.setPen(muted_text_color)
        painter.setFont(QFont("Sans Serif", 10))
        if not days or max_total <= 0:
            painter.drawText(self.rect(), Qt.AlignCenter, "Noch keine Sessions")
            return

        left, top, right, bottom = 92, 18, 22, 42
        chart_width = max(1, self.width() - left - right)
        chart_height = max(1, self.height() - top - bottom)
        row_height = chart_height / len(days)

        for index, day in enumerate(days):
            y = int(top + index * row_height)
            center_y = int(y + row_height * 0.5)
            painter.setPen(label_color)
            painter.drawText(8, center_y + 5, day["date"][5:])

            x = left
            total_width = int((day["total"] / max_total) * chart_width)
            if total_width == 0 and day["total"] > 0:
                total_width = 2

            for activity_index, activity in enumerate(activities):
                durations = day["activities"].get(activity, [])
                duration = sum(durations)
                if duration <= 0:
                    continue
                segment_width = int((duration / day["total"]) * total_width)
                if segment_width == 0:
                    segment_width = 1
                painter.fillRect(
                    x,
                    center_y - 8,
                    segment_width,
                    16,
                    self.COLORS[activity_index % len(self.COLORS)],
                )
                x += segment_width

            painter.setPen(value_color)
            painter.drawText(left + total_width + 8, center_y + 5, f"{day['total']:.1f}m")

        legend_y = self.height() - 22
        legend_x = left
        painter.setFont(QFont("Sans Serif", 9))
        for activity_index, activity in enumerate(activities[:6]):
            color = self.COLORS[activity_index % len(self.COLORS)]
            painter.fillRect(legend_x, legend_y - 9, 10, 10, color)
            painter.setPen(legend_color)
            painter.drawText(legend_x + 15, legend_y, activity[:16])
            legend_x += 95


class SnapoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Snapo")
        self.resize(1040, 720)

        database.init_db(sync_enabled=False)
        self.session = SessionTimer()
        self.settings = QSettings("Snapo", "Snapo")
        self.dark_mode = self.settings.value("dark_mode", True, type=bool)
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self.on_tick)
        self.sound = None

        self.build_ui()
        self.apply_styles()
        self.refresh_data()
        self.update_timer_view()

    def create_sound(self):
        from PySide6.QtMultimedia import QSoundEffect

        sound_path = os.path.join(BASE_DIR, "bell.wav")
        effect = QSoundEffect(self)
        if os.path.exists(sound_path):
            effect.setSource(QUrl.fromLocalFile(sound_path))
            effect.setVolume(0.55)
        return effect

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Snapo")
        title.setObjectName("AppTitle")
        self.status_label = QLabel("Bereit")
        self.status_label.setObjectName("StatusLabel")
        title_block.addWidget(title)
        title_block.addWidget(self.status_label)
        header.addLayout(title_block)
        header.addStretch()
        self.dark_mode_checkbox = QCheckBox("Dark Mode")
        self.dark_mode_checkbox.setChecked(self.dark_mode)
        header.addWidget(self.dark_mode_checkbox)
        self.sync_checkbox = QCheckBox("Git-Sync")
        self.sync_checkbox.setToolTip("Aktiviert Git pull/add/commit/push beim Speichern.")
        header.addWidget(self.sync_checkbox)
        layout.addLayout(header)

        main_grid = QGridLayout()
        main_grid.setHorizontalSpacing(16)
        main_grid.setVerticalSpacing(16)
        layout.addLayout(main_grid, 1)

        timer_panel = self.panel()
        timer_layout = QVBoxLayout(timer_panel)
        timer_layout.setSpacing(14)

        self.phase_label = QLabel("Fokus")
        self.phase_label.setObjectName("PhaseLabel")
        self.time_label = QLabel("25:00")
        self.time_label.setObjectName("TimeLabel")
        self.meta_label = QLabel("Zyklus 1 von 4")
        self.meta_label.setObjectName("MetaLabel")
        timer_layout.addWidget(self.phase_label)
        timer_layout.addWidget(self.time_label)
        timer_layout.addWidget(self.meta_label)

        controls = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.pause_button = QPushButton("Pause")
        self.log_button = QPushButton("Log & Stop")
        self.cancel_button = QPushButton("Abbrechen")
        controls.addWidget(self.start_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.log_button)
        controls.addWidget(self.cancel_button)
        timer_layout.addLayout(controls)

        settings = QGridLayout()
        self.activity_input = QLineEdit("tech")
        self.comment_input = QLineEdit()
        self.comment_input.setPlaceholderText("Kommentar")
        self.work_spin = self.spin(1, 240, 25)
        self.break_spin = self.spin(1, 120, 5)
        self.long_break_spin = self.spin(1, 180, 15)
        self.cycles_spin = self.spin(1, 24, 4)
        self.endless_checkbox = QCheckBox("Endless")

        settings.addWidget(QLabel("Aktivität"), 0, 0)
        settings.addWidget(self.activity_input, 0, 1, 1, 3)
        settings.addWidget(QLabel("Kommentar"), 1, 0)
        settings.addWidget(self.comment_input, 1, 1, 1, 3)
        settings.addWidget(QLabel("Work"), 2, 0)
        settings.addWidget(self.work_spin, 2, 1)
        settings.addWidget(QLabel("Break"), 2, 2)
        settings.addWidget(self.break_spin, 2, 3)
        settings.addWidget(QLabel("Long"), 3, 0)
        settings.addWidget(self.long_break_spin, 3, 1)
        settings.addWidget(QLabel("Cycles"), 3, 2)
        settings.addWidget(self.cycles_spin, 3, 3)
        settings.addWidget(self.endless_checkbox, 4, 0, 1, 2)
        timer_layout.addLayout(settings)

        self.chart = DailyChart()
        chart_panel = self.panel()
        chart_layout = QVBoxLayout(chart_panel)
        chart_title = QLabel("Tagesstatistik")
        chart_title.setObjectName("SectionTitle")
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(self.chart, 1)

        table_panel = self.panel()
        table_layout = QVBoxLayout(table_panel)
        table_header = QHBoxLayout()
        table_title = QLabel("Letzte Sessions")
        table_title.setObjectName("SectionTitle")
        refresh_button = QPushButton("Aktualisieren")
        refresh_button.clicked.connect(self.refresh_data)
        table_header.addWidget(table_title)
        table_header.addStretch()
        table_header.addWidget(refresh_button)
        table_layout.addLayout(table_header)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Datum", "Zeit", "Aktivität", "Min", "Kommentar"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        table_layout.addWidget(self.table)

        main_grid.addWidget(timer_panel, 0, 0)
        main_grid.addWidget(chart_panel, 0, 1)
        main_grid.addWidget(table_panel, 1, 0, 1, 2)
        main_grid.setColumnStretch(0, 1)
        main_grid.setColumnStretch(1, 1)
        main_grid.setRowStretch(1, 1)

        self.start_button.clicked.connect(self.start_session)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.log_button.clicked.connect(self.log_and_stop)
        self.cancel_button.clicked.connect(self.cancel_session)
        self.endless_checkbox.toggled.connect(self.update_timer_view)
        self.dark_mode_checkbox.toggled.connect(self.set_dark_mode)

    def panel(self):
        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setFrameShape(QFrame.StyledPanel)
        return frame

    def spin(self, minimum, maximum, value):
        spinbox = QSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setValue(value)
        spinbox.setSuffix(" min")
        return spinbox

    def config_from_ui(self):
        activity = self.activity_input.text().strip() or "default"
        return TimerConfig(
            work_minutes=self.work_spin.value(),
            break_minutes=self.break_spin.value(),
            long_break_minutes=self.long_break_spin.value(),
            cycles=self.cycles_spin.value(),
            activity=activity,
            comment=self.comment_input.text().strip(),
            endless=self.endless_checkbox.isChecked(),
        )

    def start_session(self):
        self.session.start(self.config_from_ui())
        self.tick_timer.start()
        self.status_label.setText("Session läuft")
        self.update_timer_view()

    def toggle_pause(self):
        if not self.session.running:
            return
        if self.session.paused:
            self.session.resume()
            self.status_label.setText("Session läuft")
        else:
            self.session.pause()
            self.status_label.setText("Pausiert")
        self.update_timer_view()

    def log_and_stop(self):
        minutes = self.session.elapsed_minutes()
        if minutes <= 0:
            QMessageBox.information(self, "Snapo", "Es gibt noch keine Arbeitszeit zum Speichern.")
            return
        database.log_session(
            self.session.config.activity,
            minutes,
            self.session.config.comment,
            sync_enabled=self.sync_checkbox.isChecked(),
        )
        self.session.stop()
        self.tick_timer.stop()
        self.status_label.setText("Session gespeichert")
        self.refresh_data()
        self.update_timer_view()

    def cancel_session(self):
        self.session.stop()
        self.tick_timer.stop()
        self.status_label.setText("Abgebrochen")
        self.update_timer_view()

    def on_tick(self):
        transition = self.session.tick()
        if transition:
            self.play_notification()
            if transition["next"] == "complete":
                database.log_session(
                    self.session.config.activity,
                    self.session.elapsed_minutes(),
                    self.session.config.comment,
                    sync_enabled=self.sync_checkbox.isChecked(),
                )
                self.tick_timer.stop()
                self.status_label.setText("Session abgeschlossen und gespeichert")
                self.refresh_data()
        self.update_timer_view()

    def play_notification(self):
        if self.sound is None:
            try:
                self.sound = self.create_sound()
            except Exception:
                self.sound = None
        if self.sound is not None and self.sound.source().isValid():
            self.sound.play()
        else:
            QApplication.beep()

    def refresh_data(self):
        data = plot.get_data()
        self.chart.set_summary(plot.summarize_daily(data))
        rows = database.fetch_sessions(limit=50)
        self.table.setRowCount(len(rows))
        for row_index, (_id, date, timestamp, activity, duration, comment) in enumerate(rows):
            time_text = timestamp[11:16] if timestamp else ""
            values = [date, time_text, activity, f"{float(duration):.1f}", comment or ""]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_index == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, col_index, item)

    def set_dark_mode(self, enabled):
        self.dark_mode = enabled
        self.settings.setValue("dark_mode", enabled)
        self.apply_styles()

    def update_timer_view(self):
        if self.session.running:
            phase_names = {
                "work": "Fokus",
                "break": "Pause",
                "long_break": "Lange Pause",
                "complete": "Fertig",
            }
            self.phase_label.setText(phase_names.get(self.session.phase, "Fokus"))
            self.time_label.setText(format_seconds(self.session.display_seconds()))
            self.meta_label.setText(
                f"Zyklus {self.session.cycle_index} von {self.session.config.cycles}"
                f" · Arbeit {self.session.elapsed_minutes():.1f} min"
            )
            self.pause_button.setText("Fortsetzen" if self.session.paused else "Pause")
        else:
            config = self.config_from_ui()
            self.phase_label.setText("Fokus")
            self.time_label.setText("00:00" if config.endless else format_seconds(config.work_minutes * 60))
            self.meta_label.setText(f"Zyklus 1 von {config.cycles}")
            self.pause_button.setText("Pause")

        running = self.session.running
        self.pause_button.setEnabled(running)
        self.log_button.setEnabled(running)
        self.cancel_button.setEnabled(running)
        self.start_button.setEnabled(not running)

    def apply_styles(self):
        if hasattr(self, "chart"):
            self.chart.set_dark_mode(self.dark_mode)

        if self.dark_mode:
            stylesheet = """
            QMainWindow, QWidget {
                background: #0f172a;
                color: #e5e7eb;
                font-family: Inter, Segoe UI, Sans Serif;
                font-size: 14px;
            }
            #AppTitle {
                font-size: 30px;
                font-weight: 700;
                color: #f8fafc;
            }
            #StatusLabel, #MetaLabel {
                color: #94a3b8;
            }
            #Panel {
                background: #111827;
                border: 1px solid #253247;
                border-radius: 8px;
            }
            #SectionTitle, #PhaseLabel {
                font-size: 16px;
                font-weight: 700;
                color: #f1f5f9;
            }
            #TimeLabel {
                font-size: 76px;
                font-weight: 700;
                color: #f8fafc;
            }
            QPushButton {
                background: #2563eb;
                color: #ffffff;
                border: 0;
                border-radius: 6px;
                padding: 9px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QPushButton:disabled {
                background: #334155;
                color: #94a3b8;
            }
            QLineEdit, QSpinBox {
                background: #0f172a;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #60a5fa;
            }
            QCheckBox {
                color: #dbe4ef;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #475569;
                background: #0f172a;
            }
            QCheckBox::indicator:checked {
                background: #2563eb;
                border: 1px solid #60a5fa;
            }
            QTableWidget {
                background: #0f172a;
                color: #e5e7eb;
                alternate-background-color: #111827;
                border: 1px solid #253247;
                gridline-color: #253247;
                selection-background-color: #1e40af;
                selection-color: #ffffff;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background: #1e293b;
                color: #f1f5f9;
                border: 0;
                border-bottom: 1px solid #334155;
                padding: 7px;
                font-weight: 700;
            }
            """
        else:
            stylesheet = """
            QMainWindow, QWidget {
                background: #eef2f6;
                color: #172033;
                font-family: Inter, Segoe UI, Sans Serif;
                font-size: 14px;
            }
            #AppTitle {
                font-size: 30px;
                font-weight: 700;
            }
            #StatusLabel, #MetaLabel {
                color: #64748b;
            }
            #Panel {
                background: #ffffff;
                border: 1px solid #d7dee8;
                border-radius: 8px;
            }
            #SectionTitle, #PhaseLabel {
                font-size: 16px;
                font-weight: 700;
            }
            #TimeLabel {
                font-size: 76px;
                font-weight: 700;
                color: #111827;
            }
            QPushButton {
                background: #1f6feb;
                color: white;
                border: 0;
                border-radius: 6px;
                padding: 9px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #185abc;
            }
            QPushButton:disabled {
                background: #a8b3c2;
            }
            QLineEdit, QSpinBox {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                gridline-color: #e2e8f0;
                selection-background-color: #dbeafe;
            }
            QHeaderView::section {
                background: #f1f5f9;
                border: 0;
                border-bottom: 1px solid #cbd5e1;
                padding: 7px;
                font-weight: 700;
            }
            """
        self.setStyleSheet(
            stylesheet
        )


def main():
    app = QApplication(sys.argv)
    window = SnapoWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
