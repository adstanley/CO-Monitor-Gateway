from digi.xbee.devices import XBeeDevice
from digi.xbee.models.mode import OperatingMode
import time

# Serial port settings
PORT = "COM4" 
BAUD_RATE = 9600

# First connect with current settings
# Initially create the device without specifying operating mode
device = XBeeDevice(PORT, BAUD_RATE)

try:
    # Open connection to the device
    print("Opening device...")
    device.open()
    
    # Check current API mode
    response = device.get_parameter("AP")
    current_mode = response[0] if response else 0
    print(f"Current API mode: {current_mode}")
    
    # Set to API mode without escapes (Mode 1)
    # Or use 2 for API mode with escapes
    desired_mode = 1  # or 2
    
    if current_mode != desired_mode:
        print(f"Changing API mode to {desired_mode}...")
        device.set_parameter("AP", bytearray([desired_mode]))
        
        # Apply changes (important!)
        device.apply_changes()
        print("Changes applied. Device will reset.")
        
        # Wait for the device to reset
        time.sleep(2)
        
        # Reopen with the correct mode
        device.close()
        print("Reopening with new settings...")
        
        # Now specify the operating mode explicitly based on what we set
        operating_mode = OperatingMode.API_MODE if desired_mode == 1 else OperatingMode.ESCAPED_API_MODE
        device = XBeeDevice(PORT, BAUD_RATE)
        device.open()
        
        # Verify new mode
        response = device.get_parameter("AP")
        new_mode = response[0] if response else 0
        print(f"New API mode: {new_mode}")
    else:
        print(f"API mode already set to {desired_mode}")
        
except Exception as e:
    print(f"Error: {e}")
    
finally:
    if device is not None and device.is_open():
        device.close()