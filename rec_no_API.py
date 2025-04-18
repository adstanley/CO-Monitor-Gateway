"""
XBee Transparent Mode Receiver
"""

import time
import datetime
import struct
import serial

# Define serial port settings
PORT = "COM4"       # On my windows machine typically COM3 or COM4
BAUD_RATE = 9600    # Standard baud rate for XBee
DATA_BITS = 8       # 8 data bits
STOP_BITS = 1       # 1 stop bit
PARITY = 'N'        # No parity bit
TIMEOUT = 1         # 1 second timeout

# Define struct size
INT_STRUCT_SIZE = 4

def date_time():
    """
    Get the current date and time formatted as a string
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def main():
    print("XBee Transparent Mode Receiver")
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
        
        # If sucessful print to console
        print("Serial port opened successfully.")
        print("Polling for incoming messages...") 
        print("Press Ctrl+C to exit...")
        
        # Declare a buffer to store incoming struct
        buffer = b""
        
        # State variable for struct detection
        collecting_struct = False
        
        while True:
            # Check if data is available to read
            if device.in_waiting > 0:
                # Read available data
                data = device.read(device.in_waiting)
                
                # Process each byte to detect both line-based messages and structs
                for byte in data:
                    # Convert the byte to bytes type for Python 3 compatibility
                    b = bytes([byte])
                    
                    # If we're not currently looking for a struct, check if this could be text data
                    if not collecting_struct:
                        # Add to the normal buffer
                        buffer += b
                        
                        # If we've accumulated enough data that might be a struct, analyze it
                        if len(buffer) >= INT_STRUCT_SIZE:
                            # Check if what we've received so far looks like it could be our struct format
                            # For a 4-byte integer around 2025, first bytes would likely be 0 or close to 0
                            if buffer[-INT_STRUCT_SIZE] == 0 and buffer[-INT_STRUCT_SIZE+1] == 0:
                                # This might be a struct, let's try to parse it
                                try:
                                    potential_struct = buffer[-INT_STRUCT_SIZE:]
                                    int_value = struct.unpack('>I', potential_struct)[0]
                                    timestamp = date_time()
                                    
                                    # If the value is within a reasonable range, assume it's our struct
                                    if 1000 <= int_value <= 10000:  # Adjust range as needed
                                        print(f"[{timestamp}] Received integer as struct: {int_value}")
                                        # Remove the struct from the buffer
                                        buffer = buffer[:-INT_STRUCT_SIZE]
                                        continue
                                    
                                except struct.error:
                                    # Not a valid struct, continue processing as text
                                    pass
                    
                    # Process complete lines if we have a newline character
                    if b'\n' in buffer:
                        lines = buffer.split(b'\n')
                        # Keep the last incomplete line in the buffer
                        buffer = lines[-1]
                        
                        # Process all complete lines
                        for line in lines[:-1]:
                            # Get timestamp
                            timestamp = date_time()
                            
                            try:
                                # Try to decode the line as UTF-8
                                decoded_line = line.decode('utf-8').rstrip('\r')
                                print(f"[{timestamp}] Received string: {decoded_line}")
                            except UnicodeDecodeError:
                                # If not valid UTF-8, try to parse as struct first
                                if len(line) == INT_STRUCT_SIZE:
                                    try:
                                        # Format the raw bytes as hex for display
                                        raw_hex = ' '.join(f"{b:02x}" for b in line)                                        
                                        int_value = struct.unpack('>I', line)[0]
                                        
                                        print(f"[{timestamp}] Received integer as struct: {int_value} (raw bytes: {raw_hex})")
                                        
                                        continue
                                    except struct.error:
                                        pass
                                
                                # If struct parsing fails or size doesn't match, show as hex
                                hex_data = line.hex()
                                hex_data = ' '.join(hex_data[i:i+2] for i in range(0, len(hex_data), 2))
                                print(f"[{timestamp}] Received (hex): {hex_data}")
            
            # add delay to avoid deadlock/busywaiting
            time.sleep(1)
    
    # if we catch an error print it to the console 
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