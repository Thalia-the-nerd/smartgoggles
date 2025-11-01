import evdev
import asyncio
import sys
import os # Import os to check user ID

# Set a timeout for how long to wait for a key press on each device
INPUT_TIMEOUT_SECONDS = 3.0

async def listen_for_key(device):
    """Waits for a single key press event from the device."""
    try:
        async for event in device.async_read_loop():
            if event.type == evdev.ecodes.EV_KEY and event.value == 1: # Key press
                print(f"\n>>> Key Detected! Code = {event.code}")
                return True
    except (IOError, OSError) as e:
        print(f"\n (Error reading device: {e})")
        return False
    except asyncio.CancelledError:
        # This will be raised when the timeout expires
        print(f" (No input detected in {INPUT_TIMEOUT_SECONDS}s, moving on...)")
        return False
    except Exception as e:
        print(f"\n (An unexpected error occurred: {e})")
        return False

async def main():
    """Loops through each device, asking the user to test it."""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    if not devices:
        print("No input devices found. Make sure your keypad is plugged in.")
        return

    print("--- Interactive Keypad Test (Timeout Version) ---")
    print(f"I will test each device, waiting {INPUT_TIMEOUT_SECONDS} seconds for a key press.")
    print("When prompted, press any key on your numeric keypad.")
    print("If it's not the keypad, just wait for the timeout.\n")

    for device in devices:
        print("---------------------------------")
        print(f"TESTING DEVICE: {device.path} ({device.name})")
        print("Press a key on your keypad now...")
        
        try:
            # Create the listener task
            listen_task = asyncio.create_task(listen_for_key(device))
            
            # Wait for it to complete, but with a timeout
            await asyncio.wait_for(listen_task, timeout=INPUT_TIMEOUT_SECONDS)
            
            key_pressed = listen_task.result()
            
            if key_pressed:
                while True:
                    choice = input("Is this your keypad? (y/n): ").strip().lower()
                    if choice == 'y':
                        print("\n--- SUCCESS! ---")
                        print("Your keypad was found at the following path:")
                        print(f"PATH: {device.path}")
                        print("\nPlease copy the 'PATH' value above (e.g., /dev/input/eventX) and paste it in our chat.")
                        return device.path
                    elif choice == 'n':
                        print("OK, moving to the next device...")
                        break
                    else:
                        print("Please enter 'y' or 'n'.")

        except asyncio.TimeoutError:
            # This catches the timeout from wait_for
            # The listen_task will be cancelled, and its own handler will print the message.
            pass
        except (IOError, OSError) as e:
            print(f" (Cannot access device: {e}, skipping...)")
            continue
        except Exception as e:
            print(f" (An unexpected error occurred: {e}, skipping...)")
            continue
    
    print("\n---------------------------------")
    print("Finished testing all devices, but the keypad was not confirmed.")
    print("Please make sure it's plugged in and try running the script again.")
    return None

if __name__ == "__main__":
    if sys.version_info < (3, 7):
        print("This script requires Python 3.7+ to run.")
        sys.exit(1)
        
    try:
        if os.geteuid() != 0:
            print("ERROR: This script must be run with sudo to access /dev/input/ devices.")
            print("Please run again using: sudo python3 key_test.py")
            sys.exit(1)
    except AttributeError:
        print("Warning: Could not determine user privileges. Assuming root.")
        
    try:
        device_path = asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
        sys.exit(0)


