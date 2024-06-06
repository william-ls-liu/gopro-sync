# Author: William Liu <liwi@ohsu.edu>

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from open_gopro import WirelessGoPro, Params
import asyncio
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
import logging
from pynput import keyboard
import os
from datetime import datetime


async def scan_for_cameras() -> dict[str, BLEDevice]:
    """Scan for available GoPro cameras."""

    devices: dict[str, BLEDevice] = dict()

    def scan_callback(device, advertising_data):
        if device.name and device.name != "Unknown":
            logger.info(f"Discovered {device}")
            devices[device.name] = device

    async with BleakScanner(scan_callback, service_uuids=['0000fea6-0000-1000-8000-00805f9b34fb']):
        for i in range(1, 100):
            await asyncio.sleep(0.1)

    return devices


def device_table(devices: dict[str, BLEDevice]):
    """Display table with GoPro cameras found by scanning."""

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Device Name")
    table.add_column("Bluetooth Address", style="dim")
    for name, device in devices.items():
        table.add_row(
            name, device.address
        )
    console.print(table)


async def connected_camera_table(connected_cameras: dict[str, WirelessGoPro]):
    """Display a table with infor about each connected GoPro."""

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Camera Name")
    table.add_column("Battery Level")
    table.add_column("Space Remaining on SD Card (mb)")
    for name, camera in connected_cameras.items():
        batt = await (camera.ble_status.int_batt_per).get_value()
        sdcard = await (camera.ble_status.space_rem).get_value()
        table.add_row(
            name,
            str(batt.data) + "%",
            str(sdcard.data / 1000)
        )

    console.print(table)


def prompt_device_selection(devices: dict[str, BLEDevice]) -> str | None:
    """Prompt user to choose which device(s) to connect to."""

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
        console.log(
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
):
    """Connect to camera(s) based on user input."""

    if connect_prompt == "None":
        pass
    else:
        with console.status("Connecting to cameras..."):
            if connect_prompt == "All":
                for name in found_devices.keys():
                    if name in connected_cameras:
                        console.log(f"{name} is already connected")
                        continue
                    try:
                        cam = WirelessGoPro(target=name, enable_wifi=False)
                        await cam.open()
                        console.log(f"Connected to {name}")
                        connected_cameras[name] = cam
                    except Exception as e:
                        logging.error(f"Failed to connect to camera, error message: {e}.")
                        console.log(e)
            else:
                if connect_prompt in connected_cameras:
                    pass
                else:
                    try:
                        cam = WirelessGoPro(target=connect_prompt, enable_wifi=False)
                        await cam.open()
                        console.log(f"Connected to {connect_prompt}")
                        connected_cameras[connect_prompt] = cam
                    except Exception as e:
                        logging.error(f"Failed to connect to camera, error message: {e}.")
                        console.log(e)


async def disconnect_cameras(connected_cameras: dict[str, WirelessGoPro], quit_flag: bool = False) -> None:
    """Disconnect all currently connected GoPro cameras.

    It is very important to call the close() method on each WirelessGoPro
    instance. If the connection is not closed gracefully it can cause issues
    the next time you try to connect to the camera. Then you have to reset the
    connections from the camera and re-pair with the computer.
    """

    if connected_cameras:
        with console.status("Disconnecting from cameras..."):
            disconnected = list()
            for cam in connected_cameras:
                await connected_cameras[cam].close()
                disconnected.append(cam)
                logging.info(f"Disconnected from {cam}.")
                console.log(f"Disconnected from {cam}")
            for cam in disconnected:
                del connected_cameras[cam]
    else:
        if not quit_flag:
            console.log("No cameras are currently connected")


async def wait_for_camera_ready(connected_cameras: dict[str, WirelessGoPro]) -> bool:
    """Make sure cameras are ready to receive commands."""

    if connected_cameras:
        not_ready = 0
        for name, cam in connected_cameras.items():
            logging.info(f"Check if {name} is ready...")
            ready = False
            for _ in range(10):
                status = await cam.is_ready
                if status:
                    ready = True
                    break
                await asyncio.sleep(1)
            if ready:
                logging.info(f"{name} is ready.")
                console.log(f"{name} is ready!")
            else:
                not_ready += 1
                logging.info(f"{name} is not ready.")
                console.log(f"Timed-out waiting for {name} to be ready. Try again.")
        if not_ready != 0:
            return False
        else:
            return True
    else:
        console.log("No cameras are connected!")
        return False


async def record(connected_cameras: dict[str, WirelessGoPro], timeout: float | None = None):
    """Listen for the Page Down keycode to start/stop a recording.

    Parameters
    ----------
    connected_cameras : dict[str, WirelessGoPro]
        Dictionary containining the WirelessGoPro instances of the currently
        connected cameras.
    timeout : int | float
        Maximum time, in seconds, to wait for the key press before cancelling.
    """

    correct_key: bool = False
    while not correct_key:
        with console.status("Waiting for start trigger. Switch application focus to Mobility Lab"):
            # the key release after pressing enter can trigger the event listner, so sleep for a few seconds to ensure
            # no keys are actively being pressed
            await asyncio.sleep(2)
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
            correct_key = True
            console.log("Cancelling recording.")
            logging.info("Recording cancelled.")

    # Wait for stop trigger
    correct_key = False
    while not correct_key:
        with console.status("Recording..."):
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


async def main() -> None:
    """"""
    console.rule("Welcome to the GoPro Camera Control App")
    logging.info("Entered main, starting app.")
    running = True
    connected_cameras: dict[str, WirelessGoPro] = dict()
    logging.info(f"The following cameras are connected {connected_cameras}.")
    ready_to_record: bool = False  # flag to set when cameras are connected and not busy
    logging.info(f"The ready_to_record status is {ready_to_record}")

    while running:
        first_action = Prompt.ask(
            "What would you like to do?",
            choices=["Connect", "Disconnect", "View", "Record", "Help", "Quit"]
        )
        logging.info(f"First action prompt was displayed, response was {first_action}.")

        if first_action == "Connect":
            found_devices: dict[str, BLEDevice] = dict()
            with console.status("Scanning for cameras..", spinner="shark"):
                found_devices = await scan_for_cameras()
            logging.info(f"Scanning found the following cameras: {found_devices}.")
            device_table(found_devices)
            connect_prompt = prompt_device_selection(found_devices)
            logging.info(f"The connect prompt was displayed, user chose: {connect_prompt}.")
            if connect_prompt is not None:
                await connect_camera(found_devices, connected_cameras, connect_prompt)

        elif first_action == "Disconnect":
            await disconnect_cameras(connected_cameras)

        elif first_action == "View":
            if connected_cameras:
                await connected_camera_table(connected_cameras)
            else:
                console.log("No cameras currently connected")

        elif first_action == "Record":
            if connected_cameras:
                ready_to_record = await wait_for_camera_ready(connected_cameras)
                logging.info(f"Ready to record is {ready_to_record}.")
                if ready_to_record:
                    console.log("All cameras are ready to record.")
                    await record(connected_cameras)
                else:
                    console.log("At least one of the cameras is not ready to receive commands. Try again.")
            else:
                console.log("No cameras currently connected")

        elif first_action == "Help":
            console.print("Need to add help info")

        elif first_action == "Quit":
            await disconnect_cameras(connected_cameras, quit_flag=True)
            logging.info("Quitting application.")
            console.log("Goodbye!")
            await asyncio.sleep(1)
            running = False


if __name__ == "__main__":
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
