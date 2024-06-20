# Author: William Liu <liwi@ohsu.edu>

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from open_gopro import WirelessGoPro, Params, constants, GoProResp
from open_gopro.exceptions import FailedToFindDevice, ConnectFailed
import asyncio
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
import logging
from pynput import keyboard
import os
from datetime import datetime


async def scan_for_cameras() -> dict[str, BLEDevice]:
    """Scan for available GoPro cameras.

    Returns
    -------
    dict[str, BLEDevice]
        Dictionary of GoPro cameras that were found during scanning.
    """

    devices: dict[str, BLEDevice] = dict()

    def scan_callback(device, advertising_data):
        if device.name and device.name != "Unknown":
            logger.info(f"Discovered {device}")
            devices[device.name] = device

    async with BleakScanner(scan_callback, service_uuids=['0000fea6-0000-1000-8000-00805f9b34fb']):
        for i in range(1, 100):
            await asyncio.sleep(0.1)

    return devices


def device_table(devices: dict[str, BLEDevice]) -> None:
    """Display table with GoPro cameras found by scanning.

    Parameters
    ----------
    devices : dict[str, BLEDevice]
        Dictionary of GoPro cameras found during scanning.
    """

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Device Name")
    table.add_column("Bluetooth Address", style="dim")
    for name, device in devices.items():
        table.add_row(
            name, device.address
        )
    console.print(table)


async def get_camera_battery(cam: WirelessGoPro) -> int:
    """Get current battery level in percent."""

    batt = await (cam.ble_status.int_batt_per).get_value()
    return batt.data


async def verify_battery(cam: WirelessGoPro) -> tuple[bool, int]:
    """Check if battery is above 20%."""

    batt = await get_camera_battery(cam)
    if batt <= 20:
        return False, batt

    return True, batt


async def get_camera_remaining_storage(cam: WirelessGoPro) -> int:
    """Get remaining space on SD card, in kilobytes."""

    storage = await (cam.ble_status.space_rem).get_value()
    return storage.data


async def verify_storage(cam: WirelessGoPro) -> tuple[bool, int]:
    """Check if storage is above 1 GB."""

    storage = await get_camera_remaining_storage(cam)
    if storage <= 1E6:
        return False, storage

    return True, storage


async def connected_camera_table(connected_cameras: dict[str, WirelessGoPro]) -> None:
    """Display a table with infor about each connected GoPro.

    Parameters
    ----------
    connected_cameras : dict[str, WirelessGoPro]
        Dictionary of currently connected cameras, where key is the camera name
        and value is the `WirelessGoPro` instance.
    """

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Camera Name")
    table.add_column("Battery Level")
    table.add_column("Space Remaining on SD Card (mb)")
    for name, camera in connected_cameras.items():
        batt = await get_camera_battery(camera)
        sdcard = await get_camera_remaining_storage(camera)
        table.add_row(
            name,
            str(batt) + "%",
            str(sdcard / 1000)
        )

    console.print(table)


def prompt_device_selection(devices: dict[str, BLEDevice]) -> str | None:
    """Prompt user to choose which device(s) to connect to.

    Parameters
    ----------
    devices : dict[str, BLEDevice]
        Dictionary of GoPro cameras found during scanning.

    Returns
    -------
    str | None
        A string representing the user's choice, or `None` if no cameras were
        found during scanning.
    """

    if devices:
        choices = ["All", "None"]
        choices.extend([n for n in devices.keys()])
        prompt = Prompt.ask(
            "Do you want to connect to any of the found devices?",
            console=console,
            choices=choices
        )

        return prompt

    else:
        console.print(
            """No cameras were found. Make sure:
            1) All cameras are turned on
            2) The computer's bluetooth is turned on
            3) If this is the first time connecting to a camera, it must be in pairing mode"""
        )

        return


async def connect_camera(
        found_devices: dict[str, BLEDevice],
        connected_cameras: dict[str, WirelessGoPro],
        connect_prompt: str
) -> None:
    """Connect to camera(s) based on user input.

    Parameters
    ----------
    found_devices : dict[str, BLEDevice]
        Dictionary of GoPro cameras that were discovered during scanning.
    connected_cameras : dict[str, WirelessGoPro]
        Dictionary of currently connected cameras, where key is the camera name
        and value is the `WirelessGoPro` instance.
    connect_prompt : str
        User input from the connect prompt.
    """

    if connect_prompt == "None":
        pass
    else:
        retry: bool = True
        while retry:
            missed_connections: list = []
            retry = False
            with console.status("Connecting to cameras...", spinner='bouncingBar'):
                if connect_prompt == "All":
                    for name in found_devices.keys():
                        if name in connected_cameras:
                            console.print(f"{name} is already connected.")
                            continue
                        try:
                            cam = WirelessGoPro(target=name, enable_wifi=False)
                            await cam.open()
                            console.print(f"Connected to {name}")
                            connected_cameras[name] = cam
                        except FailedToFindDevice:
                            logging.error(f"Failed to find {name}.")
                            missed_connections.append(name)
                        except ConnectFailed:
                            logging.error(f"Failed to connect to {name}.")
                            missed_connections.append(name)
                else:
                    if connect_prompt in connected_cameras:
                        console.print(f"{connect_prompt} is already connected.")
                        retry = False
                    else:
                        try:
                            cam = WirelessGoPro(target=connect_prompt, enable_wifi=False)
                            await cam.open()
                            console.print(f"Connected to {connect_prompt}")
                            connected_cameras[connect_prompt] = cam
                        except FailedToFindDevice:
                            logging.error(f"Failed to find {connect_prompt}.")
                            missed_connections.append(connect_prompt)
                        except ConnectFailed:
                            logging.error(f"Failed to connect to {connect_prompt}.")
                            missed_connections.append(connect_prompt)
            if missed_connections:
                retry = Confirm.ask(
                    f"Could not connect to the following camera(s): {missed_connections}. Retry?"
                )


async def disconnect_cameras(connected_cameras: dict[str, WirelessGoPro], quit_flag: bool = False) -> None:
    """Disconnect all currently connected GoPro cameras.

    It is very important to call the close() method on each WirelessGoPro
    instance. If the connection is not closed gracefully it can cause issues
    the next time you try to connect to the camera. Then you have to reset the
    connections from the camera and re-pair with the computer.

    Parameters
    ----------
    connected_cameras : dict[str, WirelessGoPro]
        Dictionary of currently connected cameras, where key is the camera name
        and value is the `WirelessGoPro` instance.
    quit_flag : bool
        Indicates whether this method was called when user is trying to quit the
        application or merely disconnect the cameras without quitting.
    """

    if connected_cameras:
        with console.status("Disconnecting from cameras...", spinner='bouncingBar'):
            disconnected = list()
            for cam in connected_cameras:
                await connected_cameras[cam].close()
                disconnected.append(cam)
                logging.info(f"Disconnected from {cam}.")
                console.print(f"Disconnected from {cam}")
            for cam in disconnected:
                del connected_cameras[cam]
    else:
        if not quit_flag:
            console.print("No cameras are currently connected")


async def ready_to_record(connected_cameras: dict[str, WirelessGoPro]) -> bool:
    """Make sure cameras are ready to start recording.

    This includes checking for battery life and SD card space remaining, to
    prevent starting a recording where the camera might run out of battery or
    SD card space.

    Parameters
    ----------
    connected_cameras : dict[str, WirelessGoPro]
        Dictionary of currently connected cameras, where key is the camera name
        and value is the `WirelessGoPro` instance.
    """

    if connected_cameras:
        not_ready: int = 0
        for name, cam in connected_cameras.items():
            logging.info(f"Checking if {name} is ready...")
            ready: bool = False
            batt_ready: bool = False
            sdcard_ready: bool = False

            for _ in range(10):
                status = await (cam.ble_status.system_ready).get_value()
                if status:
                    ready = True
                    batt_ready, batt_percent = await verify_battery(cam)
                    sdcard_ready, sdcard_remaining = await verify_storage(cam)
                    break
                await asyncio.sleep(1)

            if (ready, batt_ready, sdcard_ready) == (True, True, True):
                logging.info(
                    f"{name} is ready, the battery is at {batt_percent}%, and the SD card has"
                    f" {sdcard_remaining} kb remaining."
                )
                console.print(f"{name} is ready!")
            elif (ready, batt_ready, sdcard_ready) == (True, True, False):
                not_ready += 1
                logging.info(
                    f"{name} is ready, the battery is at {batt_percent}%, and the SD card has"
                    f" {sdcard_remaining} kb remaining."
                )
                console.print(
                    f"{name} only has {sdcard_remaining / 1E6} GB remaining, quit the app and remove some of the video"
                    " files before proceeding."
                )
            elif (ready, batt_ready, sdcard_ready) == (True, False, False):
                not_ready += 1
                logging.info(
                    f"{name} is ready, the battery is at {batt_percent}%, and the SD card has"
                    f" {sdcard_remaining} kb remaining."
                )
                console.print(
                    f"{name} only has {sdcard_remaining / 1E6} GB remaining and the battery is at {batt_percent}%."
                    " Quit the app, remove some of the video files, and change the battery before proceeding."
                )
            else:
                not_ready += 1
                logging.info(
                    f"{name} is not ready, the battery is at {batt_percent}%, and the SD card has {sdcard_remaining} kb"
                    " remaining."
                )
                console.print(f"{name} is not ready. Please try again.")

        if not_ready != 0:
            return False
        else:
            return True
    else:
        console.print("No cameras are connected!")
        return False


async def record(connected_cameras: dict[str, WirelessGoPro], timeout: float | None = None) -> None:
    """Listen for the Page Down keycode to start/stop a recording.

    Parameters
    ----------
    connected_cameras : dict[str, WirelessGoPro]
        Dictionary containining the WirelessGoPro instances of the currently
        connected cameras.
    timeout : int | float
        Maximum time, in seconds, to wait for the key press before cancelling.
    """
    # The key release after pressing ENTER can trigger the event listner, so sleep for a second to ensure
    # no keys are actively being pressed
    await asyncio.sleep(1)

    correct_key: bool = False

    while not correct_key:
        with console.status(
            "Switch application focus to Mobility Lab, then press > on remote to start recording. Press ESC to cancel.",
            spinner='bouncingBar'
        ):
            logging.info("Starting keyboard listener, waiting for start trigger.")
            with keyboard.Events() as events:
                event = events.get(timeout)
            logging.info(f"Keyboard event was: {event.key}.")
        if event.key == keyboard.Key.page_down:
            correct_key = True
            tasks = []
            async with asyncio.TaskGroup() as tg:  # once context manager exits all tasks are awaited
                for cam in connected_cameras.values():
                    tasks.append(tg.create_task(cam.ble_command.set_shutter(shutter=Params.Toggle.ENABLE)))
            logging.info("Recording started.")
        elif event.key == keyboard.Key.esc:
            console.print("Recording cancelled.")
            logging.info("Recording cancelled.")
            return

    # Wait for stop trigger
    correct_key = False
    while not correct_key:
        with console.status("Recording... Press > on remote to stop recording.", spinner='bouncingBar'):
            logging.info("Starting keyboard listener, waiting for stop trigger.")
            with keyboard.Events() as events:
                event = events.get(timeout)
            logging.info(f"Keyboard event was: {event.key}.")
        if event.key == keyboard.Key.page_down:
            correct_key = True
            tasks = []
            async with asyncio.TaskGroup() as tg:  # once context manager exits all tasks are awaited
                for cam in connected_cameras.values():
                    tasks.append(tg.create_task(cam.ble_command.set_shutter(shutter=Params.Toggle.DISABLE)))


async def enforce_camera_settings(connected_cameras: dict[str, WirelessGoPro], retries: int = 5) -> None:
    """Ensure all cameras are recording with the same video settings.

    The standard settings for all users are:

    Parameters
    ----------
    connected_cameras : dict[str, WirelessGoPro]
        Dictionary containining the WirelessGoPro instances of the currently
        connected cameras.
    """

    # Standard settings
    settings = {
        'load_preset_group': Params.PresetGroup.VIDEO,
        'camera_ux_mode': Params.CameraUxMode.PRO,
        'video_profile': Params.VideoProfile.STANDARD,
        'video_aspect_ratio': Params.VideoAspectRatio.RATIO_16_9,
        'resolution': Params.Resolution.RES_1080,
        'fps': Params.FPS.FPS_60,
        'video_field_of_view': Params.VideoFOV.LINEAR,
        'hypersmooth': Params.HypersmoothMode.OFF,
        'hindsight': Params.Hindsight.OFF,
        'bit_depth': Params.BitDepth.BIT_8,
        'bit_rate': Params.BitRate.HIGH,
        'auto_off': Params.AutoOff.MIN_30
    }

    def _check_response(resp: GoProResp, setting: str, name: str, retry: int) -> bool:
        if resp.status != constants.ErrorCode.SUCCESS:
            logging.error(f"{name} did not succeed in changing the {setting} on try #{retry + 1}.")
            return False

        logging.info(f"{name} changed {setting} successfully on try #{retry + 1}.")
        return True

    with console.status("Verifying camera settings...", spinner='bouncingBar'):
        for name, cam in connected_cameras.items():
            for setting in settings:
                for i in range(retries):
                    if setting == 'load_preset_group':  # ensure camera is in video mode
                        resp = await (cam.ble_command.load_preset_group(group=settings[setting]))
                    else:
                        resp = await (getattr(cam.ble_setting, setting)).set(settings[setting])
                    if _check_response(resp, setting, name, i):
                        break
                    if i == (retries - 1):
                        logging.warning(f"{name} did not succeed in changing the {setting}.")
                        console.print(
                            f"{name} did not succeed in changing the {setting}. Try re-connecting to the cameras."
                        )


async def main() -> None:
    """Entrypoint for the asynchronous event loop."""

    console.rule("Welcome to the GoPro Camera Control App")
    logging.info("Entered main, starting app.")
    running = True
    connected_cameras: dict[str, WirelessGoPro] = dict()
    logging.info(f"The following cameras are connected {connected_cameras}.")
    ready: bool = False  # flag to set when cameras are connected and not busy
    logging.info(f"The ready_to_record status is {ready}")

    while running:
        first_action = Prompt.ask(
            "What would you like to do?",
            choices=["Connect", "Disconnect", "View", "Record", "Help", "Quit"]
        )
        logging.info(f"First action prompt was displayed, response was {first_action}.")

        if first_action == "Connect":
            found_devices: dict[str, BLEDevice] = dict()
            with console.status("Scanning for cameras..", spinner='bouncingBar'):
                found_devices = await scan_for_cameras()
            logging.info(f"Scanning found the following cameras: {found_devices}.")
            if found_devices:
                device_table(found_devices)
            connect_prompt = prompt_device_selection(found_devices)
            logging.info(f"The connect prompt was displayed, user chose: {connect_prompt}.")
            if connect_prompt is not None:
                await connect_camera(found_devices, connected_cameras, connect_prompt)
                await enforce_camera_settings(connected_cameras)

        elif first_action == "Disconnect":
            await disconnect_cameras(connected_cameras)

        elif first_action == "View":
            if connected_cameras:
                await connected_camera_table(connected_cameras)
            else:
                console.print("No cameras currently connected")

        elif first_action == "Record":
            if connected_cameras:
                ready = await ready_to_record(connected_cameras)
                logging.info(f"Ready to record is {ready}.")
                if ready:
                    await record(connected_cameras)
                else:
                    console.print("At least one of the cameras is not ready to receive commands. Try again.")
            else:
                console.print("No cameras currently connected")

        elif first_action == "Help":
            console.print("Need to add help info")

        elif first_action == "Quit":
            await disconnect_cameras(connected_cameras, quit_flag=True)
            logging.info("Quitting application.")
            console.print("Goodbye!")
            await asyncio.sleep(1)
            running = False


cwd = os.getcwd()
log_folder = os.path.join(cwd, 'log')
if not os.path.exists(log_folder):
    os.mkdir(log_folder)
now = datetime.now()
now_str = now.strftime('%Y-%m-%d_%H-%M-%S')
log_fname = os.path.join(log_folder, f'{now_str}.log')
logger = logging.getLogger()
logging.basicConfig(
    filename=log_fname,
    encoding='utf-8',
    format='%(asctime)s:%(levelname)s:%(message)s',
    level=logging.INFO
)
console = Console()

loop = asyncio.new_event_loop()
loop.run_until_complete(main())
