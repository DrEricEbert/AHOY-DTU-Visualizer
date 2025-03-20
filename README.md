# AHOY-DTU-Visualizer
Simple Visualizer for [AHOY-DTU](https://ahoydtu.de/) and [GitHub](https://github.com/lumapu/ahoy?tab=readme-ov-file).
Values are shown live in tachometer form. Values are stored as JSON with time stamp in SQLite database in advanced case.

Install requirements.txt

* `pip install --upgrade -r requirements.txt`

Run AhoyDTU_Tacho_Live_Save.py for a while and use f.e. [SQLite-Studio](https://sqlitestudio.pl/) to view produced ahoydtu.sqlite file.

Use AhoyDTU_SQLite_Plot_and_Stats.py to have a time series visualization, histogram and descriptive stats.
