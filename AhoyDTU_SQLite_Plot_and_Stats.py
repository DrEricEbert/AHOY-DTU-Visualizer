#!/usr/bin/env python3
import sys
import sqlite3
import json
import datetime
import statistics

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QTabWidget,
    QFileDialog,
    QScrollArea,
)
from PyQt6.QtCore import Qt

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

# =============================================================================
# Helper: Load and process data from SQLite database
# =============================================================================
def load_data(db_file="ahoydtu.sqlite"):
    """
    Reads all records from the SQLite database (table 'data' with fields
    'timestamp' (ISO‑format) and 'json_data' (a JSON string)), parses the json
    and extracts, for each measurement field (e.g., "U_DC", "I_DC", etc.),
    a list of tuples (timestamp, value).
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, json_data FROM data ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    
    data_dict = {}
    for ts_str, json_str in rows:
        try:
            ts = datetime.datetime.fromisoformat(ts_str)
        except Exception as err:
            print("Error parsing timestamp:", err)
            continue
        try:
            rec = json.loads(json_str)
        except Exception as err:
            print("Error parsing JSON:", err)
            continue
        
        # Assume that relevant data is in rec["inverter"][0]
        inverter_data = rec.get("inverter", [])
        if not inverter_data or not isinstance(inverter_data, list):
            continue
        measurements = inverter_data[0]
        seen = {}  # use first occurrence for a given field
        for meas in measurements:
            fld = meas.get("fld")
            val = meas.get("val")
            if fld and fld not in seen:
                seen[fld] = val
        for fld, val in seen.items():
            try:
                f_val = float(val)
            except Exception:
                continue
            if fld not in data_dict:
                data_dict[fld] = []
            data_dict[fld].append((ts, f_val))
    for fld in data_dict:
        data_dict[fld].sort(key=lambda x: x[0])
    return data_dict

# =============================================================================
# PlotWindow: A separate window to display a matplotlib Figure.
# =============================================================================
class PlotWindow(QWidget):
    def __init__(self, title: str, fig: plt.Figure):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        self.canvas = FigureCanvas(fig)
        layout.addWidget(self.canvas)
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save as Image")
        save_btn.clicked.connect(self.save_image)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def save_image(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Plot as Image", "", "PNG Files (*.png);;All Files (*)"
        )
        if filename:
            try:
                self.canvas.figure.savefig(filename)
            except Exception as e:
                print("Error saving image:", e)

# =============================================================================
# Main Window
# =============================================================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQLite Data Viewer & Analysis")
        self.resize(1200, 900)
        full_data = load_data()
        
        # Partition data: dynamic if values change, static otherwise
        self.dynamic_data = {}
        self.static_data = {}
        for key, measurements in full_data.items():
            values = [val for (_, val) in measurements]
            if len(set(values)) > 1:
                self.dynamic_data[key] = measurements
            else:
                self.static_data[key] = measurements
        
        # Create main layout with TabWidget and Save buttons
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- Tab 1: Plot-Matrix ---
        self.plot_matrix_tab = QWidget()
        self.setup_plot_matrix_tab()
        self.tabs.addTab(self.plot_matrix_tab, "Plot‑Matrix")
        
        # --- Tab 2: Histogramme ---
        self.histogram_tab = QWidget()
        self.setup_histogram_tab()
        self.tabs.addTab(self.histogram_tab, "Histogramme")
        
        # --- Tab 3: Text ---
        self.text_tab = QWidget()
        self.setup_text_tab()
        self.tabs.addTab(self.text_tab, "Text")
        
        # --- Save Buttons at Bottom ---
        btn_layout = QHBoxLayout()
        self.save_img_btn = QPushButton("Save Combined as Image")
        self.save_img_btn.clicked.connect(self.save_combined_image)
        btn_layout.addWidget(self.save_img_btn)
        
        self.save_text_btn = QPushButton("Save Text as File")
        self.save_text_btn.clicked.connect(self.save_text)
        btn_layout.addWidget(self.save_text_btn)
        
        main_layout.addLayout(btn_layout)
    
    # -------------------------------------------------------------------------
    # Setup Tab 1: Plot-Matrix (each button opens a separate plot window)
    # Only first 9 dynamic curves are used.
    # -------------------------------------------------------------------------
    def setup_plot_matrix_tab(self):
        layout = QGridLayout(self.plot_matrix_tab)
        self.plot_matrix_tab.setLayout(layout)
        keys = sorted(self.dynamic_data.keys())[:9]
        self.plot_buttons = {}  # store button references keyed by curve name
        for idx, key in enumerate(keys):
            btn = QPushButton(key)
            btn.clicked.connect(lambda checked, k=key: self.open_plot_window(k, plot_type="plot"))
            row = idx // 3
            col = idx % 3
            layout.addWidget(btn, row, col)
            self.plot_buttons[key] = btn

    # -------------------------------------------------------------------------
    # Setup Tab 2: Histogramme (each button opens a separate histogram window)
    # -------------------------------------------------------------------------
    def setup_histogram_tab(self):
        layout = QGridLayout(self.histogram_tab)
        self.histogram_tab.setLayout(layout)
        keys = sorted(self.dynamic_data.keys())[:9]
        self.hist_buttons = {}
        for idx, key in enumerate(keys):
            btn = QPushButton(key)
            btn.clicked.connect(lambda checked, k=key: self.open_plot_window(k, plot_type="histogram"))
            row = idx // 3
            col = idx % 3
            layout.addWidget(btn, row, col)
            self.hist_buttons[key] = btn

    # -------------------------------------------------------------------------
    # Setup Tab 3: Text (show static curves and descriptive stats for dynamic)
    # -------------------------------------------------------------------------
    def setup_text_tab(self):
        layout = QVBoxLayout(self.text_tab)
        self.text_tab.setLayout(layout)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        self.generate_text_output()

    # -------------------------------------------------------------------------
    # Generate text output: static curves and descriptive stats for dynamic curves.
    # -------------------------------------------------------------------------
    def generate_text_output(self):
        output = ""
        if not self.static_data:
            output += "No static curves found.\n"
        else:
            output += "Static curves (constant values):\n"
            for key in sorted(self.static_data.keys()):
                measurements = self.static_data[key]
                ts, value = measurements[0]
                output += f"{key}: {value} (recorded at {ts.isoformat()})\n"
        if self.dynamic_data:
            output += "\nDescriptive statistics for dynamic curves:\n"
            for key in sorted(self.dynamic_data.keys()):
                values = [v for (_, v) in self.dynamic_data[key]]
                if not values:
                    continue
                try:
                    mean_val = statistics.mean(values)
                except Exception:
                    mean_val = 0
                try:
                    stdev_val = statistics.stdev(values) if len(values) > 1 else 0
                except Exception:
                    stdev_val = 0
                median_val = statistics.median(values)
                min_val = min(values)
                max_val = max(values)
                
                output += f"\n{key}:\n"
                output += f"  Count: {len(values)}\n"
                output += f"  Mean: {mean_val:.2f}\n"
                output += f"  Std Dev: {stdev_val:.2f}\n"
                output += f"  Median: {median_val:.2f}\n"
                output += f"  Min: {min_val:.2f}\n"
                output += f"  Max: {max_val:.2f}\n"
        self.text_edit.setPlainText(output)

    # -------------------------------------------------------------------------
    # Open a separate window with the plot.
    # plot_type is either "plot" (bar chart over time) or "histogram".
    # -------------------------------------------------------------------------
    def open_plot_window(self, key, plot_type="plot"):
        data = self.dynamic_data.get(key, [])
        if not data:
            return
        fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
        if plot_type == "plot":
            times, values = zip(*data)
            ax.bar(times, values, width=0.01)
            ax.set_title(key)
            ax.set_ylabel(key)
            ax.xaxis_date()
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            for label in ax.get_xticklabels():
                label.set_rotation(45)
        elif plot_type == "histogram":
            values = [v for (_, v) in data]
            ax.hist(values, bins=20, edgecolor="black")
            ax.set_title(f"Histogram: {key}")
            ax.set_xlabel(key)
            ax.set_ylabel("Frequency")
        fig.tight_layout()
        # Create and show the plot window
        win = PlotWindow(f"{key} - {plot_type}", fig)
        win.show()
        # Keep a reference so that it is not garbage-collected
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        # We store the window reference dynamically in self
        if not hasattr(self, "open_windows"):
            self.open_windows = []
        self.open_windows.append(win)

    # -------------------------------------------------------------------------
    # Save combined image for currently active tab (Plot‑Matrix or Histogram)
    # It creates a 3x3 figure (for up to 9 dynamic curves) and saves it.
    # -------------------------------------------------------------------------
    def save_combined_image(self):
        current_index = self.tabs.currentIndex()
        # We only allow saving combined image for plots and histograms tabs
        if current_index not in [0, 1]:
            return
        # Determine which type to plot
        plot_type = "plot" if current_index == 0 else "histogram"
        keys = sorted(self.dynamic_data.keys())[:9]
        num_plots = len(keys)
        # Create a 3x3 grid figure regardless of how many curves are present.
        fig, axes = plt.subplots(nrows=3, ncols=3, figsize=(12, 8), dpi=100)
        # Flatten the axes regardless of type:
        if hasattr(axes, "flat"):
            flat_axes = list(axes.flat)
        else:
            flat_axes = [ax for row in axes for ax in row]
        for i, ax in enumerate(flat_axes):
            ax.cla()  # clear contents
            if i < num_plots:
                key = keys[i]
                data = self.dynamic_data[key]
                if plot_type == "plot":
                    times, values = zip(*data)
                    ax.bar(times, values, width=0.01)
                    ax.set_title(key, fontsize=10)
                    ax.set_ylabel(key)
                    ax.xaxis_date()
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                    for label in ax.get_xticklabels():
                        label.set_rotation(45)
                elif plot_type == "histogram":
                    values = [v for (_, v) in data]
                    ax.hist(values, bins=20, edgecolor="black")
                    ax.set_title(f"Histogram: {key}", fontsize=10)
                    ax.set_xlabel(key)
                    ax.set_ylabel("Frequency")
            else:
                ax.set_visible(False)
        fig.tight_layout()
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Combined Image", "", "PNG Files (*.png);;All Files (*)"
        )
        if filename:
            try:
                fig.savefig(filename)
                plt.close(fig)
            except Exception as e:
                print("Error saving combined image:", e)

    # -------------------------------------------------------------------------
    # Save the text content of the Text tab to a file.
    # -------------------------------------------------------------------------
    def save_text(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Text as File", "", "Text Files (*.txt);;All Files (*)"
        )
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(self.text_edit.toPlainText())
            except Exception as e:
                print("Error saving text file:", e)

# =============================================================================
# Main Program
# =============================================================================
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
