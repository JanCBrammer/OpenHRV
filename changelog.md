# Changelog

### Version 1.1.0 (December 15 2024)
+ enhancement: Computing HRV as exponentially weighted moving average (https://en.wikipedia.org/wiki/Exponential_smoothing).
+ enhancement: Accepting Decathlon HR sensor (thanks S73ph4n).

### Version 1.0.1 (November 30 2024)
+ enhancement: Relaxed Python version constraints.
+ enhancement: Bumped PySide6 to version 6.8.
+ enhancement: Bumped Python to version 3.12.
+ bugfix: Improved sensor UUID validation (thanks Mirkan Çalışkan (mirkancal)).

### Version 1.0.0 (April 29 2024)
+ enhancement: Added docs on building macOS with PyInstaller in order to deal with Bluetooth permissions (thanks cyclemaxwell).
+ enhancement: Show version in GUI.
+ enhancement: Removed PyQtGraph and NumPy dependencies.
+ enhancement: Bumped PySide6 to version 6.7.0.
+ enhancement: Bumped Python to version 3.11.

### Version 0.2.0 (April 23, 2022)
+ enhancement: Removed recording of Redis channels (removed Redis dependency).
+ enhancement: Handling Bluetooth connection with QtBluetooth instead of bleak (removed bleak dependency).

### Version 0.1.3 (January 08, 2022)
+ enhancement: Improved Bluetooth connection (thanks Marc Schlaich (schlamar)).
+ bugfix: No more connection attempt with empty address menu.

### Version 0.1.2 (May 18, 2021)
+ enhancement: Local HRV is now averaged over a fixed window of 15 seconds. Removed slider for HRV mean window size.
+ enhancement: Status messages on application state are now displayed in the GUI.
+ enhancement: Added recording- and Redis interface features (undocumented at time of release).
+ enhancement: Rejecting some artifacts in inter-beat-intervals as well as local HRV.
+ bugfix: Made validation of sensor addresses platform-specific (thanks Alexander Weuthen (alexweuthen)).

### Version 0.1.1 (January 13, 2021)
+ enhancement: Visibility of breathing pacer can be toggled.
+ enhancement: Made range of breathing pacer rates more granular (step size .5 instead of 1).

### Version 0.1.0 (January 07, 2021)
+ enhancement: Initial release.
