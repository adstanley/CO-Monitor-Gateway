"""
XBee API Mode Receiver
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
    Handles both string messages and numeric values (as strings).
    """
    # Get current timestamp
    timestamp = date_time()
    
    # Get the sender's address
    sender = xbee_message.remote_device.get_64bit_addr()
    
    # Get the data
    data = xbee_message.data
    
    # use try except to handle errors
    try:
        # Try to decode as a string
        decoded_data = data.decode('utf-8')
        
        # Numbers are cast to string when sent. Check if recieved string is a number
        if decoded_data.isdigit():
            # Convert to integer
            number = int(decoded_data)
            
            # Print the number with timestamp and sender info
            print(f"[{timestamp}] From {sender}: Received number: {number}")
        else:
            
            # Print the string with timestamp and sender info
            print(f"[{timestamp}] From {sender}: Received string: {decoded_data}")
      
    except Exception as e:
        print(f"Error decoding data: {e}")
        return
    
    except UnicodeDecodeError:
        # If we can't decode as UTF-8, show as hex
        hex_data = data.hex()
        hex_data = ' '.join(hex_data[i:i+2] for i in range(0, len(hex_data), 2))
        print(f"[{timestamp}] From {sender}: (hex) {hex_data}")

def main():
    print("XBee API Mode Receiver")
    print(f"Opening XBee device on {PORT} at {BAUD_RATE} baud...")
    
    # Instantiate the XBee device
    device = XBeeDevice(PORT, BAUD_RATE)
    
    try:
        # Open the device
        device.open()
        
        # If successful, print to console.
        if device.is_open():
            print(f"Connected to XBee on {PORT} at {BAUD_RATE} baud")
        else:
            print("Failed to open XBee device")
            exit(1)
        
        # Pass the data_received function to the device
        device.add_data_received_callback(data_received)
        
        # Print message to indicate we are listening for incoming messages
        print("Listening for incoming messages... Press Ctrl+C to exit.")
        
        # Small delay to prevent busy waiting
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        # Always close the device
        if device is not None and device.is_open():
            device.close()
            print("XBee device closed")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript terminated by user")