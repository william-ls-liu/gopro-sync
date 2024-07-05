# gopro-sync
gopro-sync is a simple command line interface (CLI) application to wirelessly operate the shutter of multiple GoPro cameras.
The application uses the [Open GoPro Python SDK](https://github.com/gopro/OpenGoPro/tree/main/demos/python/sdk_wireless_camera_control) to control the GoPro cameras and [Rich](https://github.com/Textualize/rich) to provide the
CLI user interface.

The application is intended to provide synchronized recording of multiple GoPro cameras.

> **Heads up!** The application provides "synchronization" in the sense that it sends the command to trigger each
> camera's shutter at the same time. The Open GoPro SDK utilizes **asyncio** to handle wireless communication with the
> cameras, which can result in a time difference between the start and stop time of each camera.

# Camera compatibility
The Open GoPro API is supported on all GoPro cameras since the Hero 9. Full camera compatibility details, including
required firmware versions, can be found [here](https://gopro.github.io/OpenGoPro/).

While the Open GoPro API has broad compatibility across different cameras models, the gopro-sync app has only been
tested with the **Hero 12 Black**. I suspect that other cameras models will **NOT** work with this application for the
following reason: when the application initializes a GoPro it tries to enforce standardized video settings
(fps, resolution, etc), but not all cameras models support the same settings (as far as I can tell).

# Installation
## Using the executable
The easiest way to install the gopro-sync application is to grab the latest release [here](https://github.com/william-ls-liu/gopro-sync/releases). Simply unzip the application and run the executable, that's all there is to it!
> **Heads up!** The executable is designed to run on Windows 10/11. Other Windows versions might work, but have not been
> tested. Linux and macOS are not currently supported by this installation method.

## Using Python
If you want to instead run the application via Python then you can clone this repository and install the requirements. It is recommended to use a virtual environment; check out [virtualenv](https://virtualenv.pypa.io/en/latest/) or [venv](https://docs.python.org/3/library/venv.html) if you are new to virtual environments.

This method will *probably* allow the application to run on other operating systems, provided your OS is compatible with the required Python packages. So far all testing has been done on Windows though, so I can't make any assurances of compatibility.
> **Heads up!** Open GoPro requires Python >= 3.9 and < 3.12


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
Type "Connect" into the prompt and press ENTER.

![Connecting to cameras](https://github.com/william-ls-liu/gopro-sync/blob/main/images/connect_to_cameras.gif)