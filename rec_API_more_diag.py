"""
XBee API Mode Receiver Script - Listen for incoming messages and display with timestamp
"""

import time
import datetime
from digi.xbee.devices import XBeeDevice, XBeeMessage
from digi.xbee.models.address import XBee64BitAddress

# Serial port settings
PORT = "COM4" 
BAUD_RATE = 9600

# Global variable to store the last sender address
last_sender = None

# Function to get the current date and time formatted as a string
def date_time() -> str:
    """
    Get the current date and time formatted as a string
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

# Function to handle incoming data from XBee devices
def data_received(xbee_message: XBeeMessage) -> None:
    """
    Callback when data is received from an XBee device.
    Prints the data with timestamp and sender information.
    """
    # Declare last_sender as global variable 
    global last_sender
    
    # Get current timestamp
    timestamp = date_time()
    
    # Get the sender's address
    #sender = xbee_message.remote_device.get_64bit_addr()
    # add class type to make linter happy
    sender: XBee64BitAddress = xbee_message.remote_device.get_64bit_addr()
    
    # Store the sender address if you want to log it
    last_sender = sender  
    
    # Get message and decode the data
    # use try except to handle decoding errors
    try:
        data = xbee_message.data.decode('utf-8')
        
    except UnicodeDecodeError:
        # If data can't be decoded as UTF-8 show it as hexadecimal
        # This will never get used but it is good practice to handle errors
        data = xbee_message.data.hex()
        data = ' '.join(data[i:i+2] for i in range(0, len(data), 2))
        data = f"(hex) {data}"
    
    # Print with timestamp and sender info
    print(f"[{timestamp}] From {sender}: {data}")

def main():
    print("XBee API Mode Receiver")
    print(f"Device Located at serial port {PORT} at {BAUD_RATE} baud...")
    print(f"Device Serial Number: {XBeeDevice.get_serial_number(PORT)}")
    
    # Instantiate an XBee device object
    device = XBeeDevice(PORT, BAUD_RATE)
    
    try:
        # Open the device connection
        device.open()
        print(f"Connected to XBee on {PORT} at {BAUD_RATE} baud")
        
        # Get and print this device's 64-bit address
        my_address = device.get_64bit_addr()
        print(f"My XBee 64-bit address: {my_address}")
        
        # Define the data received callback
        device.add_data_received_callback(data_received)
        
        print("Listening for incoming transmissions... Press Ctrl+C to exit.")
        
        # Keep the main thread running indefinitely
        while True:
            time.sleep(5)  # Small delay to prevent CPU hogging
            
    except Exception as e:
        # If we encounter an error print it to the console
        print(f"Error: {e}")
        
    finally:
        # When we are done close the port
        if device and device.is_open():
            device.close()
            print("XBee connection closed")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript terminated by user")