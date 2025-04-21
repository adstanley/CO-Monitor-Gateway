"""
XBee API Mode Receiver Script - Calculate transmission time from timestamped messages
"""
import time
import datetime
import json
from digi.xbee.devices import XBeeDevice
from dateutil import parser

PORT = "COM4" 
BAUD_RATE = 9600

# Global variable to store the last sender address
last_sender = None

def data_received_callback(xbee_message):
    """
    Callback when data is received from an XBee device.
    Calculates approximate transmission time.
    """
    global last_sender
    
    # Get receive timestamp
    receive_time = datetime.datetime.now()
    receive_timestamp = receive_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    # Get the sender's address
    sender = xbee_message.remote_device.get_64bit_addr()
    last_sender = sender
    
    # Get and decode the data
    try:
        data_str = xbee_message.data.decode('utf-8')
        
        # Try to parse as JSON (our timestamped message format)
        try:
            message_data = json.loads(data_str)
            send_timestamp = message_data["timestamp"]
            content = message_data["content"]
            
            # Parse the send timestamp
            send_time = parser.parse(send_timestamp)
            
            # Calculate transmission time in milliseconds
            transmission_time_ms = (receive_time - send_time).total_seconds() * 1000
            
            # Print with transmission time
            print(f"[{receive_timestamp}] From {sender}: {content}")
            print(f"  Sent at: {send_timestamp[:-3]}")
            print(f"  Approximate transmission time: {transmission_time_ms:.2f} ms")
            
        except (json.JSONDecodeError, KeyError):
            # Not our JSON format, just display as is
            print(f"[{receive_timestamp}] From {sender}: {data_str}")
            
    except UnicodeDecodeError:
        # If data can't be decoded as UTF-8, show it as hexadecimal
        data = xbee_message.data.hex()
        data = ' '.join(data[i:i+2] for i in range(0, len(data), 2))
        print(f"[{receive_timestamp}] From {sender}: (hex) {data}")

def main():
    print("XBee API Mode Receiver - Transmission Time Calculator")
    print(f"Device Located at serial port {PORT} at {BAUD_RATE} baud...")
    
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
        device.add_data_received_callback(data_received_callback)
        
        print("Listening for incoming transmissions... Press Ctrl+C to exit.")
        
        # Keep the main thread running indefinitely
        while True:
            time.sleep(0.1)  # Small delay to prevent CPU hogging
            
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