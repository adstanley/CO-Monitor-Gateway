"""
XBee API Mode Send Script - Send messages directly to a sink radio without using remote node ID
"""
from digi.xbee.devices import XBeeDevice
import time

PORT = "COM3"  
#PORT = "/dev/ttyAMA0" # For GPIO UART pins
BAUD_RATE = 9600

def main():
    print("XBee Source Device Script")
    
    # Instantiate an XBee device object
    device = XBeeDevice(PORT, BAUD_RATE)
    
    try:
        # Open the device
        device.open()
        print("XBee device opened successfully")
        
        # Loop to send data periodically to the preconfigured destination
        message_count = 0
        while True:
            try:
                # Create a message with a counter
                message_count += 1
                message = f"Data packet #{message_count} from source"
                
                # Send the data - this will use the destination address configured in XCTU
                print(f"Sending data packet: {message}")
                device.send_data(None, message.encode())
                
                # Wait between transmissions
                time.sleep(5)  # Send every 5 seconds
                
            except Exception as e:
                print(f"Error sending data: {e}")
                time.sleep(1)
                
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