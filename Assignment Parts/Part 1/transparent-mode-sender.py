"""
Xbee UART without API
"""
import time
import struct
from machine import UART

# Configure UART
uart = UART(0, 
           baudrate=9600, 
           bits=8,
           parity=None,
           stop=1,
           tx=0, 
           rx=1,
           timeout=1000)

# Add small delay for Xbee power up
time.sleep(1)

def send_string_message(text: str) -> None:
    """
    Send a string, add carriage return and line feed
    """

    # Add carriage return and line feed to message
    message = (text + "\r\n").encode('utf-8')

    # Print to console for debugging
    print(f"Sending string: {text}")

    # Write data to UART
    uart.write(message)

    # Delay for transmission
    time.sleep(1)

def send_integer(number: int) -> None:
    """
    Send an integer as a 4-byte struct
    """
    # Package integer into 4 bytes using big-endian
    binary_data = struct.pack('>I', number)

    # Print to console for debugging
    print(f"Sending integer: {number} as bytes: {binary_data}")

    # Write data to UART
    uart.write(binary_data)

    # Delay for transmission
    time.sleep(1)

# Main loop
print("XBee UART communication started")
print("Press Ctrl+C to exit script")

# Use try-except to handle interrupt
try:
    while True:
        send_string_message("Hello World")
        time.sleep(2)

        send_string_message("2025")
        time.sleep(2)

        # Send integer as raw binary data
        send_integer(2025)
        time.sleep(5)

# if we catch an error print it to console
except Exception as e:
    print(f"An error occurred: {e}")

# if we catch an interrupt print it to console
except KeyboardInterrupt:
    print("Exiting script...")
finally:
    # Close UART
    uart.deinit()
    print("UART closed")