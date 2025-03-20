#!/usr/bin/env python3
import sys
import time
import requests
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QGridLayout,
    QVBoxLayout,
    QLabel,
    QDial,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Konfiguration der Gauges: Hier wird für jedes Messfeld der minimale und maximale Wert sowie die Einheit definiert.
GAUGE_SETTINGS = {
    "U_DC": {"min": 0, "max": 50, "unit": "V"},
    "I_DC": {"min": 0, "max": 10, "unit": "A"},
    "P_DC": {"min": 0, "max": 700, "unit": "W"},
    "YieldDay": {"min": 0, "max": 2000, "unit": "Wh"},
    "YieldTotal": {"min": 0, "max": 2000, "unit": "kWh"},
    "Irradiation": {"min": 0, "max": 100, "unit": "%"},
    "U_AC": {"min": 0, "max": 300, "unit": "V"},
    "I_AC": {"min": 0, "max": 10, "unit": "A"},
    "P_AC": {"min": 0, "max": 1000, "unit": "W"},
    "Temp": {"min": 0, "max": 100, "unit": "°C"},
    "Efficiency": {"min": 0, "max": 100, "unit": "%"},
}

# -----------------------------------------------------------------------------
# Worker-Thread, um periodisch die REST-Schnittstelle abzufragen
# -----------------------------------------------------------------------------
class DataFetcher(QThread):
    # Signal, das die abgerufenen Daten (als Dictionary) sendet
    data_fetched = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True

    def run(self):
        url = "http://ahoy-dtu/api/record/live"
        while self._is_running:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    # Sende das Dictionary ins Hauptprogramm
                    self.data_fetched.emit(data)
                else:
                    print("Fehlerhafter HTTP-Status:", response.status_code)
            except Exception as err:
                print("Error beim Abruf der Daten:", err)
            # Warte 2 Sekunden bis zum nächsten Abruf
            time.sleep(2)

    def stop(self):
        self._is_running = False

# -----------------------------------------------------------------------------
# TachoWidget: Kombination aus Label, QDial und Anzeige des aktuellen Werts.
# -----------------------------------------------------------------------------
class TachoWidget(QWidget):
    def __init__(self, name, unit, min_val, max_val, parent=None):
        super().__init__(parent)

        self.name = name
        self.unit = unit
        self.min_val = min_val
        self.max_val = max_val

        # Layout des Widgets
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Überschrift (Name des Messwertes)
        self.label_name = QLabel(name)
        self.label_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_name)

        # Das QDial-Widget als Tacho-Grafik
        self.dial = QDial()
        self.dial.setNotchesVisible(True)
        self.dial.setMinimum(min_val)
        self.dial.setMaximum(max_val)
        self.dial.setEnabled(False)  # Wir steuern es nur programmatisch
        layout.addWidget(self.dial)

        # Label für den angezeigten Wert
        self.label_value = QLabel(f"{min_val} {unit}")
        self.label_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_value)

        self.setLayout(layout)

    def update_value(self, value):
        try:
            # Konvertiere den Wert in float
            fvalue = float(value)
        except ValueError:
            fvalue = 0

        # Begrenze den Wert innerhalb des definierten Bereichs:
        if fvalue < self.min_val:
            fvalue = self.min_val
        if fvalue > self.max_val:
            fvalue = self.max_val

        self.dial.setValue(int(fvalue))
        self.label_value.setText(f"{fvalue:.2f} {self.unit}")

# -----------------------------------------------------------------------------
# Hauptfenster der Applikation
# -----------------------------------------------------------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AHOY-DTU Daten")

        # Erstelle ein Grid-Layout zum anordnen der Tachos
        self.layout = QGridLayout()
        self.setLayout(self.layout)

        # Erstelle für jedes vorgegebene Messfeld ein TachoWidget
        self.tacho_widgets = {}
        row = 0
        col = 0
        for field, conf in GAUGE_SETTINGS.items():
            widget = TachoWidget(field, conf["unit"], conf["min"], conf["max"])
            self.tacho_widgets[field] = widget
            self.layout.addWidget(widget, row, col)
            col += 1
            if col >= 3:  # 3 Spalten pro Zeile (anpassen falls nötig)
                col = 0
                row += 1

        # Starte den Worker-Thread, der den REST-Endpunkt abfragt
        self.data_fetcher = DataFetcher()
        self.data_fetcher.data_fetched.connect(self.handle_data)
        self.data_fetcher.start()

    def handle_data(self, data):
        """
        Aktualisiert die Tachos anhand der neuen Daten.
        Es wird erwartet, dass das JSON-Datenformat wie folgt aussieht:
        {
           "inverter": [ [ { "fld": "<Feldname>", "unit": "<Einheit>", "val": "<Wert>" }, ... ] ]
        }
        Wir aktualisieren für jedes in GAUGE_SETTINGS definierte Feld den ersten gefundenen
        Wert.
        """
        try:
            inverter_data = data.get("inverter", [])
            if not inverter_data or not isinstance(inverter_data, list):
                return
            # Wir gehen davon aus, dass die interessante Liste im ersten Element steht.
            measurements = inverter_data[0]
            # Für jedes Messobjekt prüfen wir, ob das Feld in unseren Tachos definiert ist.
            for measurement in measurements:
                fld = measurement.get("fld")
                if fld in self.tacho_widgets:
                    val = measurement.get("val")
                    self.tacho_widgets[fld].update_value(val)
        except Exception as err:
            print("Fehler bei der Verarbeitung der Daten:", err)

    def closeEvent(self, event):
        # Beende sauber den Worker-Thread
        self.data_fetcher.stop()
        self.data_fetcher.wait()
        event.accept()

# -----------------------------------------------------------------------------
# Hauptprogrammstart
# -----------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
