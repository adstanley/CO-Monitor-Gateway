"""
XBee API Mode Receiver Script
"""

import time
import datetime
from digi.xbee.devices import XBeeDevice

# Define serial port settings
PORT = "COM4"       # On my windows machine typically COM3 or COM4
BAUD_RATE = 9600    # Standard baud rate for XBee

def date_time():
    """
    Get the current date and time formatted as a string
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def data_received(xbee_message):
    """
    Callback when data is received from an XBee device.
    Prints the data with timestamp and sender information.
    """
    # Get current timestamp
    timestamp = date_time()
    
    # Get the sending device address
    sender = xbee_message.remote_device.get_64bit_addr()
    
    # Get and decode the data
    try:
        data = xbee_message.data.decode('utf-8')
        
    except Exception as e:
        print(f"Error decoding data: {e}")
        return
    
    # Print timestamp and device info
    print(f"[{timestamp}] From {sender}: {data}")
    
    # except UnicodeDecodeError:
    #     # If data can't be decoded as UTF-8, show it as hexadecimal
    #     data = xbee_message.data.hex()
    #     data = ' '.join(data[i:i+2] for i in range(0, len(data), 2))
    #     data = f"(hex) {data}"
    

def main():
    print("XBee API Mode Receiver Script")
    
    # Instantiate the XBee device using our defined settings
    device = XBeeDevice(PORT, BAUD_RATE)
    
    try:
        # Open the device
        device.open()
        print(f"Connected to XBee on {PORT} at {BAUD_RATE} baud")
        
        # pass data_received function to the device
        device.add_data_received_callback(data_received)
        
        print("Listening for incoming messages... Press Ctrl+C to exit.")
        
        # Delay to prevent busywaiting/deadlock
        while True:
            time.sleep(1)  
            
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        # Always close the device
        if device and device.is_open():
            device.close()
            print("XBee connection closed")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript terminated by user")