<img src="https://github.com/JanCBrammer/OpenHRV/raw/main/docs/logo.png" width="125" height="125" />

# OpenHRV

A desktop application for heart rate variability (HRV) biofeedback training with ECG chest straps.

## Compatible sensors
- Polar H7, H9, H10
- Decathlon Dual HR (model ZT26D)

## Installation

It is highly recommended to install the project in a virtual Python environment,
e.g., using [conda](https://docs.python.org/3/library/venv.html) or
[venv](https://docs.python.org/3/library/venv.html).
The required Python version is specified in
[pyproject.toml](https://github.com/JanCBrammer/OpenHRV/blob/main/pyproject.toml).

In your Python environment, clone the repository, and subsequently run

```
pip install .
```

in the root of the repository. Alternatively, you can skip cloning by running

```
pip install git+https://github.com/JanCBrammer/OpenHRV.git
```

You can now start the application with

```
python -m openhrv.app
```

or alternatively, with the shortcut

```
openhrv
```
I tested `OpenHRV` on Ubuntu 24.04. It _should_ run on Windows and macOS as well, however, I haven't confirmed that myself.
If you have problems running `OpenHRV` have a look at [docs/troubleshooting.md](docs/troubleshooting.md).

## Ubuntu executable

On Ubuntu, download and run [OpenHRV.bin](https://github.com/JanCBrammer/OpenHRV/releases/latest), no installation required.

## User Guide

### Connect your ECG sensor
First make sure the sensor is paired with your computer
(i.e., find and pair the sensor in your computer's Bluetooth settings).
Then search the sensor in **OpenHRV** by clicking `Scan`. The addresses of all
paired sensors show up in the drop-down menu. Select your sensor from the
drop-down menu and click `Connect` in order to establish a connection. You can
disconnect the sensor anytime by clicking `Disconnect`. Disconnecting is useful
if you want to connect to another sensor, or if an error occurs with the connection.
Should you have problems with the connection try disconnecting, and then reconnecting
the sensor.

![connect_sensor](https://github.com/JanCBrammer/OpenHRV/raw/main/docs/connect_sensor.gif)

### Set an HRV target
You can personalize the HRV target using the `Target` slider. After you've
been training for a while you will have a good idea of what's an attainable target
for you (this can vary depending on how much sleep or coffee you had etc.). You
can adjust the target anytime if you find the current target too easy or difficult.

![adjust_hrv_target](https://github.com/JanCBrammer/OpenHRV/raw/main/docs/adjust_hrv_target.gif)

### Set a breathing pace
The breathing pacer can help you increase your HRV. Breathe out as the blue
disk shrinks and breathe in as it gets larger. Explore how different breathing rates
affect your HRV by adjusting the `Rate` slider anytime during a session. Everyone
has a personal breathing rate at which their HRV is at its highest. Usually that
rate is somewhere between 4 and 7 breaths per minute. You can also hide the pacer
by unchecking the `Show pacer` box if you want to practice regulating HRV without pacing.

![adjust_breathing_pacer](https://github.com/JanCBrammer/OpenHRV/raw/main/docs/adjust_breathing_pacer.gif)


### Biofeedback training
Below you can watch heart rate variability (HRV) biofeedback training in action. Note
how the blue heart rate curve rises and falls. These fluctuations are the "variability"
in HRV. Your goal is to get the fluctuations large and regular. As you get better at this,
the white HRV curve will go up. There is no "ideal" HRV, as in "everyone should achieve
an HRV of 500 msec". Try to increase HRV relative to what you have achieved before
and be aware that it can take a fair bit of practice to improve.

![biofeedback_demo](https://github.com/JanCBrammer/OpenHRV/raw/main/docs/biofeedback_demo.gif)
