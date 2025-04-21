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

def verify_received_frame(self, frame_bytes):
    """
    Verify if a received XBee API frame has a valid checksum and extract sender information
    
    Args:
        frame_bytes: The complete frame as bytes or bytearray
    
    Returns:
        Tuple of (is_valid, calculated_checksum, received_checksum, decoded_data, sender_info)
    """
    # Your existing code...
    
    # When extracting sender addresses, use the proper classes
    if frame_type == 0x90 and len(frame_data) >= 12:
        # 64-bit address is bytes 1-8 in frame data
        addr_64bit_bytes = frame_data[1:9]
        addr_64bit = XBee64BitAddress(addr_64bit_bytes)
        sender_info["sender_64bit"] = addr_64bit
        sender_info["sender_64bit_hex"] = str(addr_64bit)
        
        # 16-bit address is bytes 9-10 in frame data
        if len(frame_data) >= 14:
            addr_16bit_bytes = frame_data[9:11]
            addr_16bit = XBee16BitAddress(addr_16bit_bytes)
            sender_info["sender_16bit"] = addr_16bit
            sender_info["sender_16bit_hex"] = str(addr_16bit)
    
    # Rest of your code...