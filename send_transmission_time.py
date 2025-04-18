"""
XBee API Mode Send Script - Send messages with timestamps to calculate transmission time
"""
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress
import time
import datetime
import json

PORT = "COM3"  
BAUD_RATE = 9600

# The 64-bit address of the destination/sink XBee
REMOTE_DEVICE_ADDR = "0013A20042010917"

def send_message_with_timestamp(device, remote_device, message):
    """
    Send a message with the current timestamp embedded
    """
    # Get current timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    
    # Create a message dictionary with timestamp and content
    message_data = {
        "timestamp": timestamp,
        "content": message
    }
    
    # Convert to JSON string
    json_message = json.dumps(message_data)
    
    try:
        print(f"[{timestamp}] Sending message: {message}")
        device.send_data(remote_device, json_message.encode())
        print(f"Message sent successfully")
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
        
        # Create a remote device with the 64-bit address
        remote_addr = XBee64BitAddress.from_hex_string(REMOTE_DEVICE_ADDR)
        remote_device = RemoteXBeeDevice(device, remote_addr)
        
        # Define the messages to send
        string_message = "Hello World"
        integer_message = 2025
        
        message_count = 0
        print("Continuously sending messages with timestamps. Press Ctrl+C to exit.")
        
        # Continuously send both messages in a loop
        while True:
            message_count += 1
            print(f"\n--- Transmission #{message_count} ---")
            
            # Send string message
            send_message_with_timestamp(device, remote_device, string_message)
            time.sleep(2)  # Wait between transmissions
            
            # Send integer message
            send_message_with_timestamp(device, remote_device, integer_message)
            
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