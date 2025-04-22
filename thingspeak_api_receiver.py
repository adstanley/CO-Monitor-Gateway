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

# Define the ThingSpeak channel ID and Write API Key
# These will be imported from config.py or prompted from user input
CHANNEL_ID = None
WRITE_API_KEY = None

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

#TODO: make a formatting class for these funtions 
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
            print("XBee device opened successfully\n")
            
            info = self.device.get_node_id()
            print(f"Device Info: {info}")
            addr = self.device.get_64bit_addr()
            print(f"Device Address: {addr}")
            protocol = self.device.get_protocol()
            print(f"Device Protocol: {protocol}")
            mode = self.get_api_mode()
            print(f"Device API Mode: {mode}\n")
            
            # Configure the device to receive data
            self.device.add_data_received_callback(self._data_received_callback)
            print("Data receiver callback registered\n")
            
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
    
    def decode_ao_mode(self, value):
        """
        Decodes the AO mode value into a human-readable string.
        
        Args:
            value: The AO mode value (integer)
            
        Returns:
            A string describing the AO mode
        """
        AO_FLAGS = {
            0: "Explicit RX Indicator (0x91) enabled",
            1: "Supported ZDO request pass-through",
            2: "Unsupported ZDO request pass-through",
            3: "Binding request pass-through",
            4: "Echo received supported ZDO requests",
            5: "Suppress all ZDO messages and disable pass-through"
        }
        
        if value == 0:
            return "Legacy mode (0x90 packets)"
        
        return ", ".join([desc for bit, desc in AO_FLAGS.items() if value & (1 << bit)])

    def get_api_mode(self) -> str:
        """
        Gets and returns the current XBee API (AP) mode and API Output (AO) mode
        as a clean, readable string.
        """
        API_MODE_LOOKUP = {
            0: "Transparent Mode [0]",
            1: "API Mode Without Escapes [1]",
            2: "API Mode With Escapes [2]",
            3: "NA [3]",
            4: "MicroPython REPL [4]"
        }

        try:
            api_mode = self.device.get_parameter("AP")
            api_mode = api_mode[0] if api_mode else 0
            desc = API_MODE_LOOKUP.get(api_mode, f"Unknown Mode [{api_mode}]")
            
            ao_mode = self.device.get_parameter("AO")
            ao_mode = ao_mode[0] if ao_mode else 0
            ao_desc = self.decode_ao_mode(ao_mode)
            
            # Return a clean formatted string instead of a dictionary
            return f"{desc}, AO={ao_mode}"
            
        except Exception as e:
            return f"Error checking API mode: {e}"
           
    # def get_api_mode(self) -> dict:
    #     """
    #     Prints and returns the current XBee API (AP) mode and API Output (AO) mode
    #     with human-readable descriptions.
    #     """

    #     API_MODE_LOOKUP = {
    #         0: "Transparent Mode [0]",
    #         1: "API Mode Without Escapes [1]",
    #         2: "API Mode With Escapes [2]",
    #         3: "NA [3]",
    #         4: "MicroPython REPL [4]"
    #     }

    #     AO_FLAGS = {
    #         0: "Explicit RX Indicator (0x91) enabled",  # Bit 0
    #         1: "Supported ZDO request pass-through",
    #         2: "Unsupported ZDO request pass-through",
    #         3: "Binding request pass-through",
    #         4: "Echo received supported ZDO requests",
    #         5: "Suppress all ZDO messages and disable pass-through"
    #     }

    #     def decode_ao_mode(value):
    #         if value == 0:
    #             return ["Use 0x90 RX packet (Legacy mode, no explicit addressing)"]
    #         return [desc for bit, desc in AO_FLAGS.items() if value & (1 << bit)]

    #     results = {
    #         "api_mode_value": None,
    #         "api_mode_desc": None,
    #         "api_output_mode_value": None,
    #         "api_output_mode_flags": []
    #     }

    #     try:
    #         api_mode = self.device.get_parameter("AP")
    #         api_mode = api_mode[0] if api_mode else 0
    #         desc = API_MODE_LOOKUP.get(api_mode, f"Unknown Mode [{api_mode}]")
    #         print(f"API Mode (AP): {api_mode} -> {desc}")
    #         results["api_mode_value"] = api_mode
    #         results["api_mode_desc"] = desc

    #     except Exception as e:
    #         print(f"Error checking API mode (AP): {e}")

    #     try:
    #         ao_mode = self.device.get_parameter("AO")
    #         ao_mode = ao_mode[0] if ao_mode else 0
    #         decoded = decode_ao_mode(ao_mode)
    #         print(f"API Output Mode (AO): {ao_mode}")
    #         for flag in decoded:
    #             print(f"  - {flag}")
    #         results["api_output_mode_value"] = ao_mode
    #         results["api_output_mode_flags"] = decoded

    #     except Exception as e:
    #         print(f"Error checking API output mode (AO): {e}")

    #     return results           
            
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
    
    def _data_received_callback(self, xbee_message: XBeeMessage) -> None:
        """
        Callback function with queue-based data passing
        """
        try:
            # Get the data payload directly
            data_payload = xbee_message.data
            
            # Get current timestamp
            timestamp = date_time()
            
            # Create a unique identifier for this message
            frame_identifier = bytes(data_payload)
            current_time = time.time()
            
            # Check if we've seen this exact data recently (within 1 second)
            if hasattr(self, 'last_frame_id') and hasattr(self, 'last_frame_time'):
                if self.last_frame_id == frame_identifier and (current_time - self.last_frame_time) < 1.0:
                    # This is a duplicate message, skip processing
                    return
            
            # Update the last frame hash and time
            self.last_frame_id = frame_identifier
            self.last_frame_time = current_time
            
            # Get the sender's address for logging
            # sender = xbee_message.remote_device
            
            # Get the 64-bit address as a clean string
            raw_address = str(xbee_message.remote_device)
            
            # Remove any spaces, dashes or other non-hexadecimal characters
            sender = ''.join(c for c in raw_address if c.isalnum()).upper()
            
            # Log the raw data payload first
            # print(f"DEBUG: Raw data payload: {data_payload}")
            
            with self.print_lock:
                stdout(f"[{timestamp}] Received XBee message from Address: {sender}")
                stdout(f"[{timestamp}] Data payload: {data_payload.decode('utf-8')}")
            
            # Parse the data - the parse_data function now handles bytearrays
            result = self.parse_data(data_payload)
            
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
                print(f"Failed to parse data string: {data_payload}")
                self.logger.warning(f"Failed to parse data string: {data_payload}")
                    
        except Exception as e:
            print(f"Exception in callback: {e}")
            import traceback
            traceback.print_exc()
    
    def _data_received_callback_multi(self, xbee_message: XBeeMessage) -> None:
        """
        Callback function with queue-based data passing that supports multiple nodes
        """
        try:
            # Get the data payload
            data_payload = xbee_message.data
            
            # Get the 64-bit address as a clean string
            raw_address = str(xbee_message.remote_device)
            
            # Remove any spaces, dashes or other non-hexadecimal characters
            sender = ''.join(c for c in raw_address if c.isalnum()).upper()
            
            # Get current timestamp
            timestamp = date_time()
            
            # Create a unique identifier for this message and node
            frame_identifier = (sender, bytes(data_payload))
            current_time = time.time()
            
            # Track duplicates per node using a dictionary
            if not hasattr(self, 'last_frame_ids'):
                self.last_frame_ids = {}
                self.last_frame_times = {}
                
            # Check if we've seen this exact data from this node recently (within 1 second)
            if sender in self.last_frame_ids and sender in self.last_frame_times:
                if self.last_frame_ids[sender] == bytes(data_payload) and (current_time - self.last_frame_times[sender]) < 1.0:
                    # This is a duplicate message from this node, skip processing
                    return
            
            # Update the last frame info for this node
            self.last_frame_ids[sender] = bytes(data_payload)
            self.last_frame_times[sender] = current_time
            
            # Log the raw data payload
            print(f"DEBUG: Raw data payload from {sender}: {data_payload}")
            
            with self.print_lock:
                stdout(f"[{timestamp}] Received XBee message from Address: {sender}")
                stdout(f"[{timestamp}] Data payload: {data_payload}")
            
            # Parse the data
            result = self.parse_data(data_payload)
            
            if result:
                # Extract the sensor values
                temperature, humidity, ppm = result
                # Convert Temperature to Fahrenheit
                temperatureF = round((temperature * 9/5) + 32, 2)
                
                # Store data per node in dictionaries
                if not hasattr(self, 'node_data'):
                    self.node_data = {}
                    
                # Update the data for this specific node
                self.node_data[sender] = {
                    'temperature': temperature,
                    'humidity': humidity,
                    'ppm': ppm,
                    'temperatureF': temperatureF,
                    'timestamp': timestamp
                }
                
                # Put the data into the queue for the ThingSpeak thread with node identifier
                if hasattr(self, 'data_queue'):
                    self.data_queue.put((sender, temperature, humidity, ppm, temperatureF))
                
                # Log the data
                self.logger.info(f"Received data from {sender}: Temp={temperature}°C, Humidity={humidity}%, PPM={ppm}")
                
                with self.print_lock:
                    stdout(f"[{timestamp}] Node: {sender}")
                    stdout(f"[{timestamp}] Temperature (C): {temperature}°C")
                    stdout(f"[{timestamp}] Temperature (F): {temperatureF}°F")
                    stdout(f"[{timestamp}] Humidity: {humidity}%")
                    stdout(f"[{timestamp}] CO2 PPM: {ppm} ppm\n")
            else:
                print(f"Failed to parse data string from {sender}: {data_payload}")
                self.logger.warning(f"Failed to parse data string from {sender}: {data_payload}")
                    
        except Exception as e:
            print(f"Exception in callback: {e}")
            import traceback
            traceback.print_exc()
    
    def parse_data(self, data_string) -> tuple:
        """
        Parse a data string or bytearray in the format "DATA:TEMP:26,HUM:28,PPM:1421194"
        Returns a tuple of (temperature, humidity, ppm) or None if parsing fails
        """
        try:
            # Convert bytearray to string if needed
            if isinstance(data_string, bytearray):
                data_string = data_string.decode('utf-8')
            
            # print(f"DEBUG: Parsing data (after conversion): '{data_string}'")
            
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
        # Source A = ([0x00, 0x13, 0xA2, 0x00, 0x42, 0x01, 0x09, 0x19])
        # Source B = ([0x00, 0x13, 0xA2, 0x00, 0x42, 0x01, 0x08, 0xEB])
        
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
    
def get_api_key():
    # Import ThingSpeak settings from config.py
    # If config.py is not found, prompt for input
    try:
        from config import CHANNEL_ID, WRITE_API_KEY
        print(f"✅ config.py found!")
        print(f"✅ ThingSpeak settings imported successfully!\n")
        print(f"✅ Channel ID: {CHANNEL_ID}")
        print(f"✅ API Key: {WRITE_API_KEY[:6]}{'*' * (len(WRITE_API_KEY) - 6)}\n")  # Show only first 4 chars for security
    except ImportError:
        # Prompt for input if config file not found
        print(f"❌ Warning: config.py not found!")
        print(f"❌ Please create a config.py file with the following content:")
        print("CHANNEL_ID = your_channel_id")
        print("WRITE_API_KEY = 'your_api_key'")
        
        # Exit the program or prompt for values
        import sys
        choice = input("Would you like to continue by entering values now? (y/n): ")
        if choice.lower() != 'y':
            print(f"❌ Configuration not provided. Exiting program.")
            sys.exit(1)
        
        # Get values from user input
        CHANNEL_ID = int(input("Enter your ThingSpeak Channel ID: "))
        WRITE_API_KEY = input("Enter your ThingSpeak Write API Key: ")
        print(f"✅ Configuration provided successfully!")
    
def main():
    print("XBee API Mode Receiver with ThingSpeak Integration")
    print(f"Device Located at serial port {PORT} at {BAUD_RATE} baud...\n") 
    
    # Import ThingSpeak settings from config.py
    get_api_key()
        
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
        
if __name__ == '__main__':
    main()