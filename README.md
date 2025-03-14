# gopro-sync
gopro-sync is a simple command line interface (CLI) application to wirelessly operate the shutter of multiple GoPro cameras.
The application uses the [Open GoPro Python SDK](https://github.com/gopro/OpenGoPro/tree/main/demos/python/sdk_wireless_camera_control) to control the GoPro cameras and [Rich](https://github.com/Textualize/rich) to provide the
CLI user interface.

The application is intended synchronize the recording of multiple GoPro cameras with a
[Mobility Lab](https://apdm.com/mobility/) gait analysis system.

> **Heads up!** The application provides "synchronization" in the sense that it sends the command to trigger each
> camera's shutter at the same time. The Open GoPro SDK utilizes **asyncio** to handle wireless communication with the
> cameras, which can result in a time difference between the start and stop time of each camera.

# Camera compatibility
The Open GoPro API is supported on all GoPro cameras since the Hero 9. Full camera compatibility details, including
required firmware versions, can be found [here](https://gopro.github.io/OpenGoPro/).

While the Open GoPro API has broad compatibility across different cameras models, the gopro-sync app has only been tested with the **Hero 12 Black** and the **Hero 13 Black**. I suspect that other cameras models will **NOT** work with this application for the following reason: when the application initializes a GoPro it tries to enforce standardized video settings
(fps, resolution, etc), but not all cameras models support the same settings (as far as I can tell).

# Installation
## Using the executable
The easiest way to install the gopro-sync application is to grab the latest release [here](https://github.com/william-ls-liu/gopro-sync/releases). Simply unzip the application and run the executable, that's all there is to it!
> **Heads up!** The executable is designed to run on Windows 10/11. Other Windows versions might work, but have not been
> tested. Linux and macOS are not currently supported by this installation method.

## Using Python
If you want to instead run the application via Python then you can clone this repository and install the requirements. It is recommended to use a virtual environment; check out [virtualenv](https://virtualenv.pypa.io/en/latest/) or [venv](https://docs.python.org/3/library/venv.html) if you are new to virtual environments.

This method will *probably* allow the application to run on other operating systems, provided your OS is compatible with the required Python packages. So far all testing has been done on Windows though, so I can't make any assurances of compatibility.
> **Heads up!** Open GoPro requires Python >= 3.9 and < 3.13


```console
git clone https://github.com/william-ls-liu/gopro-sync.git
cd gopro-sync
pip install -r requirements.txt
```

# Usage
## 1. Run the application
- Executable: right click the executable and select *Run as administrator*
- Python:
    ```python
    python app.py
    ```

## 2. Connect the cameras
Type *Connect* into the prompt and press ENTER. The app will conduct a Bluetooth scan and display a table of
found cameras. You can choose to connect to *All* found cameras, select an individual camera to connect to, or choose not
connect to any of the found cameras.

> **Heads up!** If you are connecting a specific GoPro camera for the first time, you need to put that camera into
> pairing mode. Consult the user manual for your specific camera model for instructions. After the initial connection is
> complete, you do not need to enter pairing mode when reconnecting that camera.

![Connecting to cameras](https://github.com/william-ls-liu/gopro-sync/blob/main/images/connect_to_cameras.gif)

## 3. Start a recording
Once you have connected the desired cameras you are ready to start a recording. Type *Record* and then press ENTER. The
app will verify that each GoPro is ready to start capturing video; if all connected cameras are ready then the app will
begin listening for the start trigger (the PageDown keycode). The app is designed around a 
[Logitech R400](https://www.logitech.com/en-us/products/presenters/r400-wireless-presenter.910-001354.html)
presentation remote. When you press the slide forward button on the remote it sends the PageDown keycode.

Pressing the slide forward button once will start a recording, and pressing it again will end the recording. Pressing
PageDown on a keyboard will also trigger a recording, but it has to be a dedicated PageDown key. If your keyboard 
requires a modifier to be held, like Fn, to access the PageDown key then the recording will not start.

> **Heads up!** The application will trigger a recording upon receipt of a PageDown keycode, even if it is not in focus.



![Recording](https://github.com/william-ls-liu/gopro-sync/blob/main/images/record.gif)