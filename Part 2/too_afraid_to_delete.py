"""
XBee API Mode Receiver Script with ThingSpeak Integration
"""

import time
import datetime
import thingspeak
import logging
import os
import json
from digi.xbee.devices import XBeeDevice, XBeeMessage
from digi.xbee.models.address import XBee64BitAddress, XBee16BitAddress
from digi.xbee.exception import XBeeException, TimeoutException
from digi.xbee.util import utils

def _data_received_callback_works_old(self, xbee_message: XBeeMessage) -> None:
        """
        Callback function that is called when data is received from an XBee device
        
        Args:
            xbee_message: The message received from the XBee network
        """
        
        # Get current timestamp
        timestamp = date_time()
        
        # Get the sender's address
        sender: XBee64BitAddress = xbee_message.remote_device.get_64bit_addr()
        
        try:
            # Extract the data from the message
            data_string = xbee_message.data.decode('utf-8')
            print(f"Received data: {data_string}")
            
            # Parse the data string
            result = self.parse_data_string(data_string)
            
            if result:
                self.temperature, self.humidity, self.ppm = result
                self.last_received_time = time.time()
                
                print("=========================================")
                print(f"[{timestamp}] Received Sensor Data From {sender}: {data_string}")
                print(f"Temperature: {self.temperature}°C")
                print(f"Humidity: {self.humidity}%")
                print(f"CO2 PPM: {self.ppm} ppm")
                print("=========================================")
                
        except Exception as e:
            print(f"Error processing received data: {e}")

def _data_received_callback_works_with_telemetry(self, xbee_message: XBeeMessage) -> None:
    """
    Enhanced callback function with frame verification
    """
    # Get raw bytes for verification
    raw_frame = xbee_message.data
    
    # First, verify the frame
    is_valid, calculated_checksum, received_checksum, decoded_data = verify_received_frame(raw_frame)
    
    print("=========================================")
    print(f"Received XBee frame: {[hex(b) for b in raw_frame]}")
    print(f"Frame valid: {is_valid}")
    print(f"Calculated checksum: 0x{calculated_checksum:02X}, Received checksum: 0x{received_checksum:02X}")
    print(f"Decoded data: {decoded_data}")
    
    # Continue with your existing processing if the frame is valid
    if is_valid:
        try:
            # Use the verified decoded data
            data_string = decoded_data
            #print(f"Processing data: {data_string}")
            
            # Parse the data string
            result = self.parse_data_string(data_string)
            
            if result:
                self.temperature, self.humidity, self.ppm = result
                self.last_received_time = time.time()
                
                print(f"Temperature: {self.temperature}°C")
                print(f"Humidity: {self.humidity}%")
                print(f"CO2 PPM: {self.ppm} ppm")
                
        except Exception as e:
            print(f"Error processing received data: {e}")
    else:
        print("Invalid frame received, skipping processing")
    print("=========================================")

def verify_received_frame(self, frame_bytes):
    """
    Verify if a received XBee API frame has a valid checksum
    
    Args:
        frame_bytes: The complete frame as bytes or bytearray
    
    Returns:
        Tuple of (is_valid, calculated_checksum, received_checksum, decoded_data)
    """
    if not frame_bytes or len(frame_bytes) < 5:
        return (False, None, None, None)
    
    # Extract frame components
    start_delimiter = frame_bytes[0]
    length_msb = frame_bytes[1]
    length_lsb = frame_bytes[2]
    length = (length_msb << 8) + length_lsb
    
    # Verify start delimiter
    if start_delimiter != 0x7E:
        return (False, None, None, "Invalid start delimiter")
    
    # Verify frame length matches expected length
    if len(frame_bytes) != length + 4:  # start delimiter + 2 length bytes + data + checksum
        return (False, None, None, f"Length mismatch: expected {length+4}, got {len(frame_bytes)}")
    
    # Extract frame data (everything between length bytes and checksum)
    frame_data = frame_bytes[3:-1]
    received_checksum = frame_bytes[-1]
    
    # Calculate checksum
    checksum = 0
    for b in frame_data:
        checksum += b
    calculated_checksum = 0xFF - (checksum & 0xFF)
    
    # Attempt to decode the data payload
    try:
        # For a 16-bit TX frame, data starts at index 5 (after frame type, frame ID, and destination)
        if len(frame_data) >= 5 and frame_data[0] == 0x01:  # TX 16-bit address frame
            data_payload = frame_data[4:]
            decoded_data = data_payload.decode('utf-8')
        else:
            decoded_data = "Unknown frame type or structure"
    except Exception as e:
        decoded_data = f"Error decoding data: {e}"
    
    return (
        calculated_checksum == received_checksum,
        calculated_checksum,
        received_checksum,
        decoded_data
    )