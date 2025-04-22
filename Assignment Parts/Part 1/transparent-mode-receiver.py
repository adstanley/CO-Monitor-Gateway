"""
XBee Transparent Mode Receiver
"""
import time
import datetime
import serial

# Define serial port settings
PORT = "COM4"       # On my windows machine typically COM3 or COM4
BAUD_RATE = 9600    # Standard baud rate for XBee
DATA_BITS = 8       # 8 data bits
STOP_BITS = 1       # 1 stop bit
PARITY = 'N'        # No parity bit
TIMEOUT = 1         # 1 second timeout

def date_time():
    """
    Get the current date and time formatted as a string
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def main():
    print("XBee Transparent Mode Receiver (No Buffer)")
    print(f"Opening serial port {PORT} at {BAUD_RATE} baud...")
    
    # Use try except to handle errors
    try:            
        # Open serial port with our defined settings
        device = serial.Serial(
            port=PORT,
            baudrate=BAUD_RATE,
            bytesize=DATA_BITS,
            parity=PARITY,
            stopbits=STOP_BITS,
            timeout=TIMEOUT
        )
        
        # If successful print to console
        print("Serial port opened successfully.")
        print("Polling for incoming messages...") 
        print("Press Ctrl+C to exit...")
        
        while True:
            # Check if data is available
            if device.in_waiting > 0:
                
                # Read available data
                data = device.read(device.in_waiting)
                
                # Get timestamp
                timestamp = date_time()
                
                # use try except to handle errors
                try:
                    # attempt to decode the data as UTF-8 and strip any trailing CR/LF
                    decoded_data = data.decode('utf-8').rstrip('\r\n')
                    
                    # Numbers are cast to string when sent 
                    # Check if received string is a number
                    if decoded_data.isdigit():
                        # Convert to integer
                        number = int(decoded_data)
                        
                        # Print the number with timestamp
                        print(f"[{timestamp}] Received number: {number}")
                    else:
                        # Print the string with timestamp
                        print(f"[{timestamp}] Received string: {decoded_data}")
                        
                except UnicodeDecodeError:
                    # If we can't decode as UTF-8, show as hex
                    hex_data = data.hex()
                    hex_data = ' '.join(hex_data[i:i+2] for i in range(0, len(hex_data), 2))
                    print(f"[{timestamp}] Received (hex): {hex_data}")
            
            # Add delay to avoid high CPU usage
            time.sleep(0.1)
    
    # If we catch an error print it to the console 
    except Exception as e:
        print(f"Error opening or using serial port: {e}")
    
    # Close the serial port if it was opened
    finally:
        if 'device' in locals() and device.is_open:
            device.close()
            print("Serial port closed")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript terminated by user")