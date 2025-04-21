"""
XBee API Mode Receiver Script with ThingSpeak Integration
"""

import time
import datetime
import thingspeak
import logging
import os
import json
import threading
import traceback
import queue
from digi.xbee.devices import XBeeDevice, XBeeMessage
from digi.xbee.models.address import XBee64BitAddress, XBee16BitAddress
from digi.xbee.exception import XBeeException, TimeoutException
from digi.xbee.util import utils

# Serial port settings
PORT = "COM4" 
BAUD_RATE = 9600

# ThingSpeak settings
CHANNEL_ID = 2925773
WRITE_API_KEY = "NN8PKRCJ2TM6NHI3"

# Global variable to store the last sender address
last_sender = None

# Get the current working directory
current_directory = os.getcwd()

# Configure logging
logging.basicConfig(
    filename=os.path.join(current_directory,'Xbee.log'),
    filemode='w',
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

def date_time() -> str:
    """
    Get the current date and time formatted as a string
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def stdout(message: str, color: str = "BLUE") -> None:
    """
    Print a message with a timestamp and custom color
    
    Args:
        color: Color name as a string (e.g., "BLUE", "RED", etc.)
        message: The message to print
    """
    # Define color mapping as a dictionary
    COLORS = {
        "RED": "\033[31m",
        "GREEN": "\033[32m",
        "YELLOW": "\033[33m",
        "BLUE": "\033[34m",
        "MAGENTA": "\033[35m",
        "CYAN": "\033[36m"
    }
    RESET = "\033[0m"
    
    # Get color code from dictionary, default to BLUE if not found
    color_code = COLORS.get(color, COLORS["BLUE"])
    
    print(f"{color_code}[{date_time()}]{RESET} {message}")

def stderr(message: str) -> None:
    """
    Print an error message with a timestamp and red color
    """
    RESET = "\033[0m"
    print(f"\033[31m[{date_time()}] ERROR: {message}\033[0m{RESET}")
    
def debug(message: str) -> None:
    """
    Print an error message with a timestamp and red color
    """
    RESET = "\033[0m"
    print(f"\033[31m[{date_time()}] DEBUG: {message}\033[0m{RESET}")

def newline(lines: int) -> None:
    """
    Print passed number of new lines
    """
    for _ in range(lines):
        print()
    
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_message = {
            'name': record.name,
            'asctime': self.formatTime(record, self.datefmt),
            'levelname': record.levelname,
            'message': record.getMessage(),
        }
        
        return json.dumps(log_message)
    
    def setup_logging(self):
        # Create a logger
        logger = logging.getLogger()

        # Create a handler that writes to the file
        file_handler = logging.FileHandler(os.path.join(current_directory, 'Xbee.json'))
        file_handler.setMode('w')

        # Set the custom JSON formatter
        json_formatter = JSONFormatter()
        file_handler.setFormatter(json_formatter)

        # Add the handler to the logger
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)

class ThingSpeakClient:
    """Class for sending data to ThingSpeak API using the official library"""
    
    def __init__(self, channel_id, write_api_key):
        """
        Initialize ThingSpeak client using the official library
        
        Available methods:
            get
            get_field
            get_field_last
            get_last_data_age
            view
            update      
            
        Args:
            channel_id: ThingSpeak channel ID
            write_api_key: ThingSpeak Write API Key
        """
        
        self.channel_id = channel_id
        self.write_api_key = write_api_key
        
        # Initialize ThingSpeak Channel
        self.channel = thingspeak.Channel(id=channel_id, api_key=write_api_key)
        
        # Store last update time for rate limiting checks
        self.last_update_time = 0
        
        # ThingSpeak's minimum update interval in seconds
        self.min_interval = 20
        
        stdout(f"ThingSpeak client initialized for channel {channel_id}")
    
    def send_data(self, temperature, humidity, ppm, temperatureF) -> int:
        """
        Send sensor data to ThingSpeak
        
        Args:
            temperature: Temperature reading
            temperatureF: Temperature reading in Fahrenheit
            humidity: Humidity reading
            ppm: CO2 PPM reading
            
        Returns:
            None
        """
        try:
            # Check if we're respecting the rate limit
            current_time = time.time()
            if current_time - self.last_update_time < self.min_interval:
                # Calculate remaining wait time
                wait_time = self.min_interval - (current_time - self.last_update_time)
                
                #print(f"Rate limit: waiting {wait_time:.1f} seconds before sending")
                time.sleep(wait_time)
            
            # Prepare the data dictionary with field1, field2 and field3
            data = {
                'field1': temperature,
                'field2': humidity,
                'field3': ppm,
                'field4': temperatureF
            }
            
            # Update the channel with our data
            response = self.channel.update(data)
            
            if response == 0:
                stdout("Error sending data to ThingSpeak")
                return None
            else:
                # stdout("Data successfully sent to ThingSpeak.")
                self.last_update_time = time.time()
                return response
                
        except Exception as e:
            print(f"Error sending data to ThingSpeak: {e}")
            return None

class APIReceiver:
    """Class for receiving sensor data from XBee in API mode using the Digi XBee library"""
    
    def __init__(self, port, baudrate=9600, thingspeak_channel_id=None, thingspeak_api_key=None):
        """
        Initialize XBee device using the Digi XBee library
        
        Args:
            port: Serial port where XBee is connected
            baudrate: Communication baudrate (default: 9600)
            thingspeak_channel_id: Optional ThingSpeak channel ID
            thingspeak_api_key: Optional ThingSpeak Write API Key
        """
        # Initialize the XBee device
        self.device = XBeeDevice(port, baudrate)
        
        # Initialize Logging
        self.logger = logging.getLogger("XBeeAPIReceiver")
        self.logger.setLevel(logging.DEBUG)
        
        # Initialize variables
        self.temperature = 0.0
        self.temperatureC= 0.0
        self.temperatureF= 0.0
        self.humidity = 0.0
        self.ppm = 0.0
        self.safe = True
        self.last_received_time = 0

        self.debug = False
        
        # Initialize ThingSpeak client if credentials are provided
        self.thingspeak_client = None
        if thingspeak_channel_id and thingspeak_api_key:
            self.thingspeak_client = ThingSpeakClient(thingspeak_channel_id, thingspeak_api_key)
            
        # Create a print lock at the class level
        self.print_lock = threading.Lock()
        self.data_lock = threading.Lock()
        
        self.logger.info("XBee API mode receiver initialized")
    

    def open(self) -> bool:
        """Open the connection to the XBee device"""
        try:
            self.device.open()
            print("XBee device opened successfully")
            
            # Configure the device to receive data
            self.device.add_data_received_callback(self._data_received_callback)
            print("Data received callback registered")
            
            return True
            
        except XBeeException as e:
            print(f"Error opening XBee device: {e}")
            return False
        
    @property
    def is_open(self) -> bool:
        """Check if the XBee device is open"""
        return self.device is not None and self.device.is_open()
            
    def close(self) -> None:
        """Close the XBee device connection safely."""
        try:
            if self.is_open:
                self.device.del_data_received_callback(self._data_received_callback)
                self.device.close()
                print("XBee device closed")
            else:
                print("Device already closed or was never opened.")
                
        except Exception as e:
            print(f"Error while closing device: {e}")        
        
    def get_device_info(self) -> dict:
        """Get information about the XBee device"""
        try:
            # Get the device information
            info = self.device.read_device_info()            
            return info
            
        except XBeeException as e:
            print(f"Error getting device info: {e}")
    
    def get_protocol(self) -> str:
        """Get the protocol used by the XBee device"""
        try:
            # Get the protocol used by the device
            protocol = self.device.get_protocol()
            return protocol
            
        except XBeeException as e:
            print(f"Error getting protocol: {e}")
           
    def get_api_mode(self) -> dict:
        """
        Prints and returns the current XBee API (AP) mode and API Output (AO) mode
        with human-readable descriptions.
        """

        API_MODE_LOOKUP = {
            0: "Transparent Mode [0]",
            1: "API Mode Without Escapes [1]",
            2: "API Mode With Escapes [2]",
            3: "NA [3]",
            4: "MicroPython REPL [4]"
        }

        AO_FLAGS = {
            0: "Explicit RX Indicator (0x91) enabled",  # Bit 0
            1: "Supported ZDO request pass-through",
            2: "Unsupported ZDO request pass-through",
            3: "Binding request pass-through",
            4: "Echo received supported ZDO requests",
            5: "Suppress all ZDO messages and disable pass-through"
        }

        def decode_ao_mode(value):
            if value == 0:
                return ["Use 0x90 RX packet (Legacy mode, no explicit addressing)"]
            return [desc for bit, desc in AO_FLAGS.items() if value & (1 << bit)]

        results = {
            "api_mode_value": None,
            "api_mode_desc": None,
            "api_output_mode_value": None,
            "api_output_mode_flags": []
        }

        try:
            api_mode = self.device.get_parameter("AP")
            api_mode = api_mode[0] if api_mode else 0
            desc = API_MODE_LOOKUP.get(api_mode, f"Unknown Mode [{api_mode}]")
            print(f"API Mode (AP): {api_mode} -> {desc}")
            results["api_mode_value"] = api_mode
            results["api_mode_desc"] = desc

        except Exception as e:
            print(f"Error checking API mode (AP): {e}")

        try:
            ao_mode = self.device.get_parameter("AO")
            ao_mode = ao_mode[0] if ao_mode else 0
            decoded = decode_ao_mode(ao_mode)
            print(f"API Output Mode (AO): {ao_mode}")
            for flag in decoded:
                print(f"  - {flag}")
            results["api_output_mode_value"] = ao_mode
            results["api_output_mode_flags"] = decoded

        except Exception as e:
            print(f"Error checking API output mode (AO): {e}")

        return results           
            
    def get_16bit_address(self) -> str:
        """Get the 16-bit address of the XBee device"""
        try:
            # Get the address of the device
            address = self.device.get_16bit_addr()
            # Convert the address to a string
            return str(address)
            
        except XBeeException as e:
            print(f"Error getting address: {e}")
            return "Unknown"
   
    def get_64bit_address(self) -> str:
        """Get the 64-bit address of the XBee device"""
        try:
            # Get the address of the device
            address = self.device.get_64bit_addr()
            # Convert the address to a string
            return str(address)
            
        except XBeeException as e:
            print(f"Error getting address: {e}")
            return "Unknown"

    # DATA SECTION   
        
    def _data_received_callback_works(self, xbee_message: XBeeMessage) -> None:
        """
        Enhanced callback function with frame verification and ThingSpeak integration
        """
        # Get raw bytes for verification
        raw_frame = xbee_message.data
        
        # Get current timestamp
        timestamp = date_time()
        
        # First, verify the frame
        is_valid, calculated_checksum, received_checksum, decoded_data = self.verify_received_frame(raw_frame)

        # Get the sender's address for logging
        sender = self.get_64bit_address()
        
        with self.print_lock:
            #print("=========================================")
            stdout(f"Received XBee frame from Address: {sender}")
            #print(f"Frame data: {[hex(b) for b in raw_frame]}")
            stdout(f"Frame valid: {is_valid}")
            stdout(f"Calculated checksum: 0x{calculated_checksum:02X}, Received checksum: 0x{received_checksum:02X}")
            stdout(f"Decoded data: {decoded_data}")
        
        # Continue with processing if the frame is valid
        if is_valid:
            try:
                # Use the verified decoded data
                data_string = decoded_data
                # print(f"Processing data: {data_string}")
                
                # Parse the data string
                result = self.parse_data(data_string)
                
                if result:
                    old_timestamp = self.last_received_time
                    with self.data_lock:
                        self.temperature, self.humidity, self.ppm = result
                        
                        # Convert Temperature to Fahrenheit
                        self.temperatureF = round((self.temperature * 9/5) + 32, 2)
                        self.last_received_time = time.time()                  
                    
                    
                    # # Log the data First then print it
                    # self.logger.info(f"Received data from {sender}: Temp={self.temperature}°C, Humidity={self.humidity}%, PPM={self.ppm}")
                    
                    with self.print_lock:                        
                        # newline(1)
                        # debug(f"Updated timestamp: old={old_timestamp}, new={self.last_received_time}\n")
                        stdout(f"Temperature (C): {self.temperature}°C")
                        stdout(f"Temperature (F): {self.temperatureF}°F")
                        stdout(f"Humidity: {self.humidity}%")
                        stdout(f"CO2 PPM: {self.ppm} ppm\n")
                    
                    # Send data to ThingSpeak if client is available
                    if self.thingspeak_client:
                        try:
                            # print(f"[{timestamp}] Sending data to ThingSpeak...")
                            success = self.thingspeak_client.send_data(
                                temperature=self.temperature,
                                humidity=self.humidity,
                                ppm=self.ppm,
                                temperatureF=self.temperatureF
                            )
                            if success:
                                # print(f"Data sent to ThingSpeak successfully.")
                                self.logger.info(f"[{timestamp}]Data sent to ThingSpeak.")
                            else:
                                # print("Failed to send data to ThingSpeak")
                                self.logger.warning("Failed to send data to ThingSpeak")
                                
                        except Exception as e:
                            print(f"Error sending data to ThingSpeak: {e}")
                            self.logger.error(f"Error sending data to ThingSpeak: {e}")
                    
                else:
                    print(f"Failed to parse data string: {data_string}")
                    self.logger.warning(f"Failed to parse data string: {data_string}")
                    
            except Exception as e:
                print(f"Error processing received data: {e}")
                self.logger.error(f"Error processing received data: {e}")
        else:
            print("Invalid frame received, skipping processing")
            self.logger.warning(f"Invalid frame received: {[hex(b) for b in raw_frame]}")
    
    def _data_received_callback_double_print(self, xbee_message: XBeeMessage) -> None:
        """
        Callback function with queue-based data passing
        """
        # Get raw bytes for verification
        raw_frame = xbee_message.data
        
        # Get current timestamp
        timestamp = date_time()
        
        # First, verify the frame
        is_valid, calculated_checksum, received_checksum, decoded_data = self.verify_received_frame(raw_frame)

        # Get the sender's address for logging
        sender = self.get_64bit_address()
        
        with self.print_lock:
            stdout(f"[{timestamp}] Received XBee frame from Address: {sender}")
            stdout(f"[{timestamp}] Frame valid: {is_valid}")
            stdout(f"[{timestamp}] Calculated checksum: 0x{calculated_checksum:02X}, Received checksum: 0x{received_checksum:02X}")
            stdout(f"[{timestamp}] Decoded data: {decoded_data}")
        
        # Continue with processing if the frame is valid
        if is_valid:
            try:
                # Use the verified decoded data
                data_string = decoded_data
                
                # Parse the data string
                result = self.parse_data(data_string)
                
                if result:
                    # Extract the sensor values
                    temperature, humidity, ppm = result
                    # Convert Temperature to Fahrenheit
                    temperatureF = round((temperature * 9/5) + 32, 2)
                    
                    # Update class variables (for other methods that might use them)
                    self.temperature = temperature
                    self.humidity = humidity
                    self.ppm = ppm
                    self.temperatureF = temperatureF
                    
                    # Put the data into the queue for the ThingSpeak thread
                    # Only add the data if the queue has been initialized
                    if hasattr(self, 'data_queue'):
                        self.data_queue.put((temperature, humidity, ppm, temperatureF))
                    
                    # Log the data first then print it
                    self.logger.info(f"Received data from {sender}: Temp={temperature}°C, Humidity={humidity}%, PPM={ppm}")
                    
                    with self.print_lock:
                        stdout(f"[{timestamp}] Temperature (C): {temperature}°C")
                        stdout(f"[{timestamp}] Temperature (F): {temperatureF}°F")
                        stdout(f"[{timestamp}] Humidity: {humidity}%")
                        stdout(f"[{timestamp}] CO2 PPM: {ppm} ppm\n")
                    
                else:
                    print(f"Failed to parse data string: {data_string}")
                    self.logger.warning(f"Failed to parse data string: {data_string}")
                    
            except Exception as e:
                print(f"Error processing received data: {e}")
                self.logger.error(f"Error processing received data: {e}")
        else:
            print("Invalid frame received, skipping processing")
            self.logger.warning(f"Invalid frame received: {[hex(b) for b in raw_frame]}")
    
    def _data_received_callback(self, xbee_message: XBeeMessage) -> None:
        """
        Callback function with queue-based data passing
        """
        # Get raw bytes for verification
        raw_frame = xbee_message.data
        
        # Get current timestamp
        timestamp = date_time()
        
        # Create a unique hash of this frame to detect duplicates
        frame_identifier = bytes(raw_frame)
        current_time = time.time()
        
        # Check if we've seen this exact frame recently (within 1 second)
        if hasattr(self, 'last_frame_id') and hasattr(self, 'last_frame_time'):
            if self.last_frame_id == frame_identifier and (current_time - self.last_frame_time) < 1.0:
                # This is a duplicate frame, skip processing
                return
        
        # Update the last frame hash and time
        self.last_frame_id = frame_identifier
        self.last_frame_time = current_time
        
        # First, verify the frame
        is_valid, calculated_checksum, received_checksum, decoded_data = self.verify_received_frame(raw_frame)

        # Get the sender's address for logging
        sender = self.get_64bit_address()
        
        with self.print_lock:
            stdout(f"[{timestamp}] Received XBee frame from Address: {sender}")
            stdout(f"[{timestamp}] Frame valid: {is_valid}")
            stdout(f"[{timestamp}] Calculated checksum: 0x{calculated_checksum:02X}, Received checksum: 0x{received_checksum:02X}")
            stdout(f"[{timestamp}] Decoded data: {decoded_data}")
        
        # Continue with processing if the frame is valid
        if is_valid:
            try:
                # Parse the data string
                result = self.parse_data(decoded_data)
                
                if result:
                    # Extract the sensor values
                    temperature, humidity, ppm = result
                    # Convert Temperature to Fahrenheit
                    temperatureF = round((temperature * 9/5) + 32, 2)
                    
                    # Update class variables (for other methods that might use them)
                    self.temperature = temperature
                    self.humidity = humidity
                    self.ppm = ppm
                    self.temperatureF = temperatureF
                    
                    # Put the data into the queue for the ThingSpeak thread
                    # Only add the data if the queue has been initialized
                    if hasattr(self, 'data_queue'):
                        self.data_queue.put((temperature, humidity, ppm, temperatureF))
                    
                    # Log the data first then print it
                    self.logger.info(f"Received data from {sender}: Temp={temperature}°C, Humidity={humidity}%, PPM={ppm}")
                    
                    with self.print_lock:
                        stdout(f"[{timestamp}] Temperature (C): {temperature}°C")
                        stdout(f"[{timestamp}] Temperature (F): {temperatureF}°F")
                        stdout(f"[{timestamp}] Humidity: {humidity}%")
                        stdout(f"[{timestamp}] CO2 PPM: {ppm} ppm\n")
                else:
                    print(f"Failed to parse data string: {decoded_data}")
                    self.logger.warning(f"Failed to parse data string: {decoded_data}")
                    
            except Exception as e:
                print(f"Error processing received data: {e}")
                self.logger.error(f"Error processing received data: {e}")
        else:
            print("Invalid frame received, skipping processing")
            self.logger.warning(f"Invalid frame received: {[hex(b) for b in raw_frame]}")
    
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
    
    def parse_data(self, data_string: str) -> tuple:
        """
        Parse a data string in the format "DATA:TEMP:26,HUM:28,PPM:1421194"
        Returns a tuple of (temperature, humidity, ppm) or None if parsing fails
        """
        try:
            # Check if the string starts with the expected prefix
            if not data_string.startswith("DATA:"):
                print(f"Invalid data format: {data_string}")
                return None
            
            # Extract the data section
            parts = data_string.split(',')
            
            # Extract temperature
            temp_part = parts[0]  # Should be "DATA:TEMP:26"
            temperature = float(temp_part.split(':')[2])
            
            # Extract humidity
            hum_part = parts[1]   # Should be "HUM:28"
            humidity = float(hum_part.split(':')[1])
            
            # Extract PPM
            ppm_part = parts[2]   # Should be "PPM:1421194"
            ppm = float(ppm_part.split(':')[1])
            
            return (temperature, humidity, ppm)
            
        except (IndexError, ValueError) as e:
            print(f"Error parsing data string: {e}")
            return None
    
    def update(self) -> bool:
        """
        Manual update method for non-callback operation
        Tries to read and process a message directly
        
        Returns True if new data was received and parsed successfully
        """
        # Make sure the device is open
        # If the device is not open, try to open it
        if not self.is_open:
            if not self.open():
                print("Failed to open XBee device")
                return False
        
        try:
            # Try to read a message synchronously (will wait up to timeout period)
            xbee_message = self.device.read_data(timeout=1)
            
            if xbee_message:
                # Process the message
                self._data_received_callback(xbee_message)
                return True
                
        except TimeoutException:
            # No message received within timeout, which is normal
            pass
        except XBeeException as e:
            print(f"Error reading data: {e}")
            
        return False
    
    def continuous_monitoring(self, check_interval=1) -> None:
        """
        Continuously monitor for incoming data
        
        This method uses the synchronous read approach rather than callbacks
        for compatibility with the original implementation
        
        Args:
            check_interval: Time between checks in seconds
        """
        print("Starting continuous API mode data reception...")
        
        # Make sure the device is open
        if not self.is_open:
            if not self.open():
                print("Failed to open XBee device")
                return
        
        try:
            while True:
                self.update()
                
                # Small delay to prevent busy waiting
                time.sleep(check_interval)
                    
        except KeyboardInterrupt:
            print("Monitoring stopped")
            
        except Exception as e:
            print(f"Error during monitoring: {e}")
            raise e
            
        finally:
            self.close()
    
    def process_thingspeak_data_norace(self):
        """
        Collect and average data points before sending to ThingSpeak
        to respect the 15-second rate limit while still capturing all sensor readings
        """
        # Initialize data collection lists
        temp_points = []
        humidity_points = []
        ppm_points = []
        tempF_points = []
        
        # Store the last time data was sent to ThingSpeak
        last_upload_time = time.time()
        
        try:
            while True:
                # If we have new data from the _data_received_callback, collect it
                if self.last_received_time > 0:
                    # Add the current readings to our collection lists
                    temp_points.append(self.temperature)
                    humidity_points.append(self.humidity)
                    ppm_points.append(self.ppm)
                    tempF_points.append(self.temperatureF)
                    
                    # Reset the last_received_time to avoid collecting the same data point multiple times
                    # (or use a flag system to track what's been collected)
                    self.last_received_time = 0
                
                current_time = time.time()
                # Check if 15 seconds have elapsed and we have data to send
                if current_time - last_upload_time >= 15 and temp_points:
                    # Calculate averages for each metric
                    avg_temp = sum(temp_points) / len(temp_points)
                    avg_humidity = sum(humidity_points) / len(humidity_points)
                    avg_ppm = sum(ppm_points) / len(ppm_points)
                    avg_tempF = sum(tempF_points) / len(tempF_points)
                    
                    # Send the averaged data to ThingSpeak
                    if self.thingspeak_client:
                        success = self.thingspeak_client.send_data(
                            temperature=avg_temp,
                            humidity=avg_humidity,
                            ppm=avg_ppm,
                            temperatureF=avg_tempF
                        )
                        
                        if success:
                            print(f"Averaged data sent to ThingSpeak: Temp={avg_temp:.1f}°C, Humidity={avg_humidity:.1f}%, PPM={avg_ppm:.1f}")
                            self.logger.info(f"Averaged data sent to ThingSpeak")
                        else:
                            print("Failed to send averaged data to ThingSpeak")
                    
                    # Reset for next cycle
                    last_upload_time = current_time
                    temp_points = []
                    humidity_points = []
                    ppm_points = []
                    tempF_points = []
                
                # Small delay to prevent CPU hogging
                time.sleep(0.1)
                    
        except KeyboardInterrupt:
            print("Data averaging process stopped")
        except Exception as e:
            print(f"Error in data averaging process: {e}")
    
    def process_thingspeak_data_race_datavar_no_update(self):
        """
        Collect and average data points before sending to ThingSpeak
        to respect the 15-second rate limit while still capturing all sensor readings
        """
        # Initialize data collection lists
        temp_points = []
        humidity_points = []
        ppm_points = []
        tempF_points = []
        
        # Store the last time data was sent to ThingSpeak
        last_upload_time = time.time()
        
        # Keep track of last processed data timestamp
        last_processed_time = 0
        
        try:
            while True:
                # Only collect new data points we haven't processed yet
                if self.last_received_time > last_processed_time:
                    # Add the current readings to our collection lists
                    temp_points.append(self.temperature)
                    humidity_points.append(self.humidity)
                    ppm_points.append(self.ppm)
                    tempF_points.append(self.temperatureF)
                    
                    # Update our tracking of what we've processed
                    last_processed_time = self.last_received_time
                
                current_time = time.time()
                # Check if 15 seconds have elapsed and we have data to send
                if current_time - last_upload_time >= 15 and temp_points:
                    # Thread safety - make a local copy of the data points to work with
                    # This prevents issues if new data arrives during processing
                    local_temp = temp_points.copy()
                    local_humidity = humidity_points.copy()
                    local_ppm = ppm_points.copy()
                    local_tempF = tempF_points.copy()
                    
                    # Clear the lists for new data collection
                    temp_points = []
                    humidity_points = []
                    ppm_points = []
                    tempF_points = []
                    
                    # Calculate averages using the local copies
                    avg_temp = sum(local_temp) / len(local_temp)
                    avg_humidity = sum(local_humidity) / len(local_humidity)
                    avg_ppm = sum(local_ppm) / len(local_ppm)
                    avg_tempF = sum(local_tempF) / len(local_tempF)
                    
                    # Send the averaged data to ThingSpeak
                    if self.thingspeak_client:
                        success = self.thingspeak_client.send_data(
                            temperature=avg_temp,
                            humidity=avg_humidity,
                            ppm=avg_ppm,
                            temperatureF=avg_tempF
                        )
                        
                        if success:
                            with self.print_lock:
                                # Pretty print
                                print("\n\033[92m" + "=" * 50)  # Green text
                                print(f"✅ THINGSPEAK UPDATE: {len(local_temp)} data points averaged")
                                print(f"   Temperature: {avg_temp:.1f}°C / {avg_tempF:.1f}°F")
                                print(f"   Humidity: {avg_humidity:.1f}%")
                                print(f"   CO2: {avg_ppm:.1f} ppm")
                                print("=" * 50 + "\033[0m\n")  # Reset text color
                                
                                # Less pretty
                                # print(f"Averaged data sent to ThingSpeak: Temp={avg_temp:.1f}°C, Humidity={avg_humidity:.1f}%, PPM={avg_ppm:.1f}")
                                # self.logger.info(f"Averaged data ({len(local_temp)} points) sent to ThingSpeak")
                        else:
                            print("Failed to send averaged data to ThingSpeak")
                    
                    # Update timestamp for next cycle
                    last_upload_time = current_time
                
                # Small delay to prevent CPU hogging
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("Data averaging process stopped")
        except Exception as e:
            print(f"Error in data averaging process: {e}")
    
    def process_thingspeak_data_loses_sync(self):
        """
        Collect and average data points before sending to ThingSpeak
        to respect the 15-second rate limit while still capturing all sensor readings
        """
        # Initialize data collection lists
        temp_points = []
        humidity_points = []
        ppm_points = []
        tempF_points = []
        
        # Store the last time data was sent to ThingSpeak
        last_upload_time = time.time()
        
        # Keep track of the last processed data timestamp
        last_processed_timestamp = 0
        
        try:
            while True:
                current_received_time = 0
                current_temp = 0
                current_humidity = 0
                current_ppm = 0
                current_tempF = 0
                
                # Safely read the current values with a lock to prevent race conditions
                with self.data_lock:
                    current_received_time = self.last_received_time
                    if current_received_time > 0 and current_received_time > last_processed_timestamp:
                        current_temp = self.temperature
                        current_humidity = self.humidity
                        current_ppm = self.ppm
                        current_tempF = self.temperatureF
                
                # Check if there's new data that we haven't processed yet
                if current_received_time > 0 and current_received_time > last_processed_timestamp:
                    # Add the current readings to our collection lists
                    temp_points.append(current_temp)
                    humidity_points.append(current_humidity)
                    ppm_points.append(current_ppm)
                    tempF_points.append(current_tempF)
                    
                    # Update the last processed timestamp
                    last_processed_timestamp = current_received_time
                    
                    # Print for debugging (optional)
                    # with self.print_lock:
                    #     print(f"Added datapoint to averaging buffer, total: {len(temp_points)}")
                
                current_time = time.time()
                # Check if 15 seconds have elapsed and we have data to send
                if current_time - last_upload_time >= 15 and temp_points:
                    # Calculate averages
                    num_points = len(temp_points)
                    avg_temp = sum(temp_points) / num_points
                    avg_humidity = sum(humidity_points) / num_points
                    avg_ppm = sum(ppm_points) / num_points
                    avg_tempF = sum(tempF_points) / num_points
                    
                    # Send the averaged data to ThingSpeak
                    if self.thingspeak_client:
                        success = self.thingspeak_client.send_data(
                            temperature=avg_temp,
                            humidity=avg_humidity,
                            ppm=avg_ppm,
                            temperatureF=avg_tempF
                        )
                        
                        if success:
                            with self.print_lock:
                                print("\n\033[92m" + "=" * 50)
                                print(f"✅ THINGSPEAK UPDATE: {num_points} data points averaged")
                                print(f"   Temperature: {avg_temp:.1f}°C / {avg_tempF:.1f}°F")
                                print(f"   Humidity: {avg_humidity:.1f}%")
                                print(f"   CO2: {avg_ppm:.1f} ppm")
                                print("=" * 50 + "\033[0m\n")
                        else:
                            with self.print_lock:
                                print("\n\033[91m" + "=" * 50) 
                                print("❌ Failed to send averaged data to ThingSpeak")
                                print("=" * 50 + "\033[0m\n")
                    
                    # Update timestamp for next cycle
                    last_upload_time = current_time
                    
                    # Clear data points for new cycle
                    temp_points = []
                    humidity_points = []
                    ppm_points = []
                    tempF_points = []
                
                # Small delay to prevent CPU hogging
                time.sleep(0.1)
                    
        except Exception as e:
            with self.print_lock:
                print(f"Error in data averaging process: {e}")
                traceback.print_exc()
    
    def process_thingspeak_data_works(self):
        """
        Collect and average data points before sending to ThingSpeak
        with enhanced frame detection
        """
        # Initialize data collection
        data_points = []  # Will store tuples of (timestamp, temp, humidity, ppm, tempF)
        last_upload_time = time.time()
        last_processed_timestamp = 0
        processed_frames = set()  # Track frame identifiers to prevent duplicates
        
        try:
            with self.print_lock:
                print("[THREAD] Starting ThingSpeak data processing thread")
            
            while True:
                current_time = time.time()
                
                # Safely get the current sensor values
                with self.data_lock:
                    current_timestamp = self.last_received_time
                    temp = self.temperature
                    humidity = self.humidity
                    ppm = self.ppm
                    tempF = self.temperatureF
                    
                    # Create a unique frame identifier (timestamp + data values)
                    # This ensures we detect unique frames even if timestamps are close
                    frame_id = f"{current_timestamp}_{temp}_{humidity}_{ppm}"
                
                # Check if we haven't processed this frame before and it's newer than our last processed timestamp
                if current_timestamp > 0 and current_timestamp > last_processed_timestamp and frame_id not in processed_frames:
                    data_points.append((current_timestamp, temp, humidity, ppm, tempF))
                    last_processed_timestamp = current_timestamp
                    processed_frames.add(frame_id)
                    
                    with self.print_lock:
                        print(f"Added datapoint to averaging buffer, total: {len(data_points)}")
                
                # Check if it's time to send data to ThingSpeak
                if current_time - last_upload_time >= 15 and data_points:
                    # with self.print_lock:
                    #     newline(1)
                    #     debug(f"Preparing to send {len(data_points)} points to ThingSpeak")
                    
                    # Calculate averages
                    num_points = len(data_points)
                    avg_temp = sum(point[1] for point in data_points) / num_points
                    avg_humidity = sum(point[2] for point in data_points) / num_points
                    avg_ppm = sum(point[3] for point in data_points) / num_points
                    avg_tempF = sum(point[4] for point in data_points) / num_points
                    
                    # Send the averaged data to ThingSpeak
                    if self.thingspeak_client:
                        success = self.thingspeak_client.send_data(
                            temperature=avg_temp,
                            humidity=avg_humidity,
                            ppm=avg_ppm,
                            temperatureF=avg_tempF
                        )
                        
                        if success:
                            with self.print_lock:
                                print("\n\033[92m" + "=" * 50)
                                print(f"✅ THINGSPEAK UPDATE: {num_points} data points averaged")
                                print(f"   Temperature: {avg_temp:.1f}°C / {avg_tempF:.1f}°F")
                                print(f"   Humidity: {avg_humidity:.1f}%")
                                print(f"   CO2: {avg_ppm:.1f} ppm")
                                print("=" * 50 + "\033[0m\n")
                        else:
                            with self.print_lock:
                                print("\n\033[91m" + "=" * 50) 
                                print("❌ Failed to send averaged data to ThingSpeak")
                                print("=" * 50 + "\033[0m\n")
                    
                    # Update timestamp for next cycle and clear data points
                    last_upload_time = current_time
                    data_points = []
                    
                    # Clear processed frames to prevent memory growth over time
                    # but keep the most recent one to prevent duplicates right after clearing
                    if processed_frames:
                        most_recent = max(processed_frames)
                        processed_frames.clear()
                        processed_frames.add(most_recent)
                
                # Small delay to prevent CPU hogging
                time.sleep(1)
        
        except Exception as e:
            with self.print_lock:
                print(f"Error in data averaging process: {e}")
                import traceback
                traceback.print_exc()
    
    def process_thingspeak_data_worksagain(self):
        """
        Process sensor data for ThingSpeak using a queue-based approach
        """
        # Create a thread-safe queue to store incoming data frames
        self.data_queue = queue.Queue()
        
        # Initialize the data collection buffer
        data_buffer = []
        last_upload_time = time.time()
        
        try:
            with self.print_lock:
                print("[THREAD] Starting ThingSpeak data processing thread")
            
            while True:
                # Check if there's new data in the queue
                try:
                    # Non-blocking queue check with a small timeout
                    new_data = self.data_queue.get(block=True, timeout=0.1)
                    
                    # Add the data point to our buffer
                    data_buffer.append(new_data)
                    
                    # Print diagnostic
                    # with self.print_lock:
                    #     print(f"Added datapoint to averaging buffer, total: {len(data_buffer)}")
                    
                    # Mark the queue task as done
                    self.data_queue.task_done()
                    
                except queue.Empty:
                    # No new data, continue with checking upload time
                    pass
                
                # Check if it's time to send data to ThingSpeak
                current_time = time.time()
                if current_time - last_upload_time >= 15 and data_buffer:
                    # Calculate averages
                    num_points = len(data_buffer)
                    avg_temp = sum(point[0] for point in data_buffer) / num_points
                    avg_humidity = sum(point[1] for point in data_buffer) / num_points
                    avg_ppm = sum(point[2] for point in data_buffer) / num_points
                    avg_tempF = sum(point[3] for point in data_buffer) / num_points
                    
                    # Send the averaged data to ThingSpeak
                    if self.thingspeak_client:
                        success = self.thingspeak_client.send_data(
                            temperature=avg_temp,
                            humidity=avg_humidity,
                            ppm=avg_ppm,
                            temperatureF=avg_tempF
                        )
                        
                        if success:
                            with self.print_lock:
                                print("\n\033[92m" + "=" * 50)
                                print(f"✅ THINGSPEAK UPDATE: {num_points} data points averaged")
                                print(f"   Temperature: {avg_temp:.1f}°C / {avg_tempF:.1f}°F")
                                print(f"   Humidity: {avg_humidity:.1f}%")
                                print(f"   CO2: {avg_ppm:.1f} ppm")
                                print("=" * 50 + "\033[0m\n")
                        else:
                            with self.print_lock:
                                print("\n\033[91m" + "=" * 50) 
                                print("❌ Failed to send averaged data to ThingSpeak")
                                print("=" * 50 + "\033[0m\n")
                    
                    # Update timestamp for next cycle and clear data buffer
                    last_upload_time = current_time
                    data_buffer = []
        
        except Exception as e:
            with self.print_lock:
                print(f"Error in data averaging process: {e}")
                traceback.print_exc()
   
    def process_thingspeak_data(self):
        """
        Process sensor data for ThingSpeak using a queue-based approach
        """
        # Create a thread-safe queue to store incoming data frames
        self.data_queue = queue.Queue()
        
        # Initialize the data collection buffer
        data_buffer = []
        last_upload_time = time.time()
        
        try:
            with self.print_lock:
                print("[THREAD] Starting ThingSpeak data processing thread")
            
            while True:
                # # Add debug printing to show current queue size
                # with self.print_lock:
                #     print(f"DEBUG: Current queue size: {self.data_queue.qsize()}")
                #     print(f"DEBUG: Current buffer size: {len(data_buffer)}")
                
                # Drain the entire queue before checking upload time
                while True:
                    try:
                        # Non-blocking queue check with a tiny timeout
                        new_data = self.data_queue.get(block=True, timeout=0.01)
                        
                        # Add the data point to our buffer
                        data_buffer.append(new_data)
                        
                        # Print diagnostic
                        # with self.print_lock:
                        #     print(f"DEBUG: Added datapoint to buffer, total: {len(data_buffer)}")
                        
                        # Mark the queue task as done
                        self.data_queue.task_done()
                        
                    except queue.Empty:
                        # No more data in queue, break the inner loop
                        break
                
                # Check if it's time to send data to ThingSpeak
                current_time = time.time()
                if current_time - last_upload_time >= 15 and data_buffer:
                    # Debug print before averaging
                    # with self.print_lock:
                    #     print(f"DEBUG: About to average {len(data_buffer)} data points")
                    
                    # Calculate averages
                    num_points = len(data_buffer)
                    avg_temp = sum(point[0] for point in data_buffer) / num_points
                    avg_humidity = sum(point[1] for point in data_buffer) / num_points
                    avg_ppm = sum(point[2] for point in data_buffer) / num_points
                    avg_tempF = sum(point[3] for point in data_buffer) / num_points
                    
                    # Send the averaged data to ThingSpeak
                    if self.thingspeak_client:
                        success = self.thingspeak_client.send_data(
                            temperature=avg_temp,
                            humidity=avg_humidity,
                            ppm=avg_ppm,
                            temperatureF=avg_tempF
                        )
                        
                        if success:
                            with self.print_lock:
                                print("\n\033[92m" + "=" * 50)
                                print(f"✅ THINGSPEAK UPDATE: {num_points} data points averaged")
                                print(f"   Temperature: {avg_temp:.1f}°C / {avg_tempF:.1f}°F")
                                print(f"   Humidity: {avg_humidity:.1f}%")
                                print(f"   CO2: {avg_ppm:.1f} ppm")
                                print("=" * 50 + "\033[0m\n")
                        else:
                            with self.print_lock:
                                print("\n\033[91m" + "=" * 50) 
                                print("❌ Failed to send averaged data to ThingSpeak")
                                print("=" * 50 + "\033[0m\n")
                    
                    # Update timestamp for next cycle and clear data buffer
                    last_upload_time = current_time
                    data_buffer = []
                
                # Sleep a bit to avoid hogging CPU
                time.sleep(1)
        
        except Exception as e:
            with self.print_lock:
                print(f"Error in data averaging process: {e}")
                traceback.print_exc()
        
    def send_data_to_node(self, destination_address, data_string):
        """
        Send data to a specific XBee node
        
        Args:
            destination_address: The 64-bit address of the destination node as a string
                                or XBee64BitAddress object
            data_string: The data string to send (will be encoded as UTF-8)
        
        Returns:
            True if the data was sent successfully, False otherwise
        """
        try:
            # Convert string address to XBee64BitAddress if needed
            if isinstance(destination_address, str):
                # Create the 64-bit destination address from string
                dest_addr = XBee64BitAddress.from_hex_string(destination_address)
            else:
                dest_addr = destination_address
                
            # Encode the data string
            data = data_string.encode('utf-8')
            
            # Send the data
            self.device._send_data_64(dest_addr, data)
            print(f"Data sent to {dest_addr}: {data_string}")
            return True
            
        except XBeeException as e:
            print(f"Error sending data: {e}")
            return False
    
    
def main():
    print("XBee API Mode Receiver with ThingSpeak Integration")
    print(f"Device Located at serial port {PORT} at {BAUD_RATE} baud...") 
        
    # Create an instance of our API receiver
    receiver = APIReceiver(
        port=PORT, 
        baudrate=BAUD_RATE,
        thingspeak_channel_id=CHANNEL_ID,
        thingspeak_api_key=WRITE_API_KEY
    )    
    
    try:
        thingspeak_thread = threading.Thread(target=receiver.process_thingspeak_data, daemon=True)
        
        print("Start thread for processing ThingSpeak data...")
        thingspeak_thread.start()       
        
        receiver.continuous_monitoring()
        
    except KeyboardInterrupt:
        print("Sigterm received, stopping...")
        
    except TimeoutException:
        print("Timeout occurred while waiting for data")
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        # close the device connection
        print("Closing XBee device...")
        if receiver is not None and receiver.is_open:
            receiver.close()
        
def test():
    """
    Test radio settings and data reception
    This function is not used in the main script but can be used for testing purposes
    """
    print("XBee API Mode Receiver test routine")
    print(f"Device Located at serial port {PORT} at {BAUD_RATE} baud...")
    
    # Create the device without opening it first
    device = APIReceiver(
        port=PORT, 
        baudrate=BAUD_RATE,
        thingspeak_channel_id=CHANNEL_ID,
        thingspeak_api_key=WRITE_API_KEY
    )
    print(f"Created XBee device object for port {PORT}")
    
    try:
        # Try to open the device
        print("Attempting to open XBee device...\n")
        
        if device.open():
            print("Successfully opened XBee device!\n")
        
        print("Getting device info...")
        device.get_device_info()
        print()
        
        print("Getting API mode...")
        device.get_api_mode()
        print()
        
        # print(f"{device.get_16bit_address()}")
        # print(f"{device.get_64bit_address()}")
        
        
        # Close the device
        device.close()
        print("Device closed")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        if device.is_open():
            device.close()
            print("Device closed due to error")
    
if __name__ == '__main__':
    main()
    # test()
