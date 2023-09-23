# Changelog

### Version 0.2.1 (Month dd, yyyy)
+ bugfix: Run on MacOS with PyInstaller in order to deal with Bluetooth permissions
+ enhancements: removed PyQtGraph and NumPy dependencies
+ enhancements: updated dependencies to latest version
+ enhancements: show version in GUI

### Version 0.2.0 (April 23, 2022)
+ enhancement: removed recording of Redis channels (removed Redis dependency).
+ enhancement: handling Bluetooth connection with QtBluetooth instead of bleak (removed bleak dependency).

### Version 0.1.3 (January 08, 2022)
+ enhancement: Improved Bluetooth connection.
+ bugfix: No more connection attempt with empty address menu.

### Version 0.1.2 (May 18, 2021)
+ enhancement: Local HRV is now averaged over a fixed window of 15 seconds. Removed slider for HRV mean window size.
+ enhancement: Status messages on application state are now displayed in the GUI.
+ enhancement: Added recording- and Redis interface features (undocumented at time of release).
+ enhancement: Rejecting some artifacts in inter-beat-intervals as well as local HRV.
+ bugfix: Made validation of sensor addresses platform-specific (thanks to Alexander Weuthen).

### Version 0.1.1 (January 13, 2021)
+ enhancement: Visibility of breathing pacer can be toggled.
+ enhancement: Made range of breathing pacer rates more granular (step size .5 instead of 1).

### Version 0.1.0 (January 07, 2021)
+ enhancement: Initial release.
