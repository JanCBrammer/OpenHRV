# Changelog

### Version 0.1.3 (January 08, 2022)
+ enhancement: Improved Bluetooth connection (c1b4211801ed9e819c7c9bfb880dd44f54e77354, 4e0b72a269d696afba89530f172c7813ae3aef9a).
+ bugfix: No more connection attempt with empty address menu (bf2e961b24612b1bb2618e49a5540724eee631ec).

### Version 0.1.2 (May 18, 2021)
+ enhancement: Local HRV is now averaged over a fixed window of 15 seconds. Removed slider for HRV mean window size.
+ enhancement: Status messages on application state are now displayed in the GUI.
+ enhancement: Added recording- and Redis interface features (undocumented at time of release).
+ enhancement: Rejecting some artifacts in inter-beat-intervals as well as local HRV.
+ bugfix: Made validation of sensor addresses platform-specific (thanks to @weuthen).

### Version 0.1.1 (January 13, 2021)
+ enhancement: Visibility of breathing pacer can be toggled.
+ enhancement: Made range of breathing pacer rates more granular (step size .5 instead of 1).

### Version 0.1.0 (January 07, 2021)
+ enhancement: Initial release.
