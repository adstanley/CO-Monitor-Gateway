"""
XBee API Mode Send Script - Continuously send specific messages to a sink radio
"""
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress
import time
import datetime

PORT = "COM4"  
#PORT = "/dev/ttyAMA0" # For GPIO UART pins
BAUD_RATE = 9600

# The 64-bit address of the destination/sink XBee
REMOTE_DEVICE_ADDR = "0013A20042010917"

def check_api_mode(device: XBeeDevice) -> bool:
    """
    Check if the XBee is in API mode
    """
    try:
        # Try to get the operating mode - this will only work if the device is open
        operating_mode = device.operating_mode()
        print(f"XBee operating mode: {operating_mode}")
        
        # Check if it's in API mode (API1 or API2)
        if "API" in str(operating_mode):
            print("XBee is in API mode - good to proceed")
            return True
        else:
            print("WARNING: XBee is NOT in API mode. Script may not function correctly.")
            return False
    except Exception as e:
        print(f"Error checking API mode: {e}")
        return False

def send_message(device, remote_device, message: str):
    """
    Send a specific message and print confirmation
    """
    # Get current timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    try:
        print(f"[{timestamp}] Sending message: {message}")
        device.send_data(remote_device, str(message).encode())
        #print(f"Message sent successfully")
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False  
    

def main():
    print("XBee Source Device Script")
    
    # Instantiate an XBee device object
    device = XBeeDevice(PORT, BAUD_RATE)
    
    try:
        # Open the device
        device.open()
        print("XBee device opened successfully")
        
        # Check if the device is in API mode
        if not check_api_mode(device):        
            print("Consider setting the XBee to API mode before continuing")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                print("Exiting application")
                return
        
        # Create a remote device with the 64-bit address
        remote_addr = XBee64BitAddress.from_hex_string(REMOTE_DEVICE_ADDR)
        remote_device = RemoteXBeeDevice(device, remote_addr)
        
        # Define the messages to send
        string_message = "Hello World"
        integer_message = 2025
        
        message_count = 0
        print("Continuously sending messages. Press Ctrl+C to exit.")
        
        # Continuously send both messages in a loop
        while True:
            # Uncomment if you want to print a header for each transmission
            # message_count += 1
            # print(f"\n--- Transmission #{message_count} ---")
            
            # Send string message
            send_message(device, remote_device, string_message)
            time.sleep(2)  # Wait between transmissions
            
            # Send integer message
            send_message(device, remote_device, integer_message)
            
            # Wait before the next round of transmissions
            time.sleep(5)  # 5-second interval between sets of messages
            
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        if device is not None and device.is_open():
            device.close()
            print("XBee device closed")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nApplication exited")