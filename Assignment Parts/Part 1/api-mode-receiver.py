"""
XBee API Mode Receiver Script - Listen for incoming messages and display with timestamp
"""

import time
import datetime
import thingspeak
import logging
import sys
from digi.xbee.devices import XBeeDevice, XBeeMessage
from digi.xbee.models.address import XBee64BitAddress
from digi.xbee.exception import XBeeException, TimeoutException

# Serial port settings
PORT = "COM4" 
BAUD_RATE = 9600

# ThingSpeak settings
CHANNEL_ID = 2925773
WRITE_API_KEY = "NN8PKRCJ2TM6NHI3"

# Global variable to store the last sender address
last_sender = None

# Configure logging
logging.basicConfig(
    filename='app.log',
    filemode='w',
    format='%(name)s - %(date)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

# Function to get the current date and time formatted as a string
def date_time() -> str:
    """
    Get the current date and time formatted as a string
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class ThingSpeakClient:
    """Class for sending data to ThingSpeak API using the official library"""
    
    def __init__(self, channel_id, write_api_key):
        """
        Initialize ThingSpeak client using the official library
        
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
        self.min_interval = 15
        
        print(f"ThingSpeak client initialized for channel {channel_id}")
    
    def send_data(self, temperature, humidity, ppm):
        """
        Send sensor data to ThingSpeak
        
        Args:
            temperature: Temperature reading
            humidity: Humidity reading
            ppm: CO2 PPM reading
            
        Returns:
            Entry ID if successful, None on error
        """
        try:
            # Check if we're respecting the rate limit
            current_time = time.time()
            if current_time - self.last_update_time < self.min_interval:
                # Calculate remaining wait time
                wait_time = self.min_interval - (current_time - self.last_update_time)
                print(f"Rate limit: waiting {wait_time:.1f} seconds before sending")
                time.sleep(wait_time)
            
            # Prepare the data dictionary with field1, field2 and field3
            data = {
                'field1': temperature,
                'field2': humidity,
                'field3': ppm
            }
            
            # Update the channel with our data
            response = self.channel.update(data)
            
            if response == 0:
                print("Error sending data to ThingSpeak")
                return None
            else:
                print(f"Data successfully sent to ThingSpeak. Entry ID: {response}")
                self.last_update_time = time.time()
                return response
                
        except Exception as e:
            print(f"Error sending data to ThingSpeak: {e}")
            return None

class APIReceiver:
    """Class for receiving sensor data from XBee in API mode using the Digi XBee library"""
    
    def __init__(self, port, baudrate=9600):
        """
        Initialize XBee device using the Digi XBee library
        
        Args:
            port: Serial port where XBee is connected (e.g., 'COM3' on Windows or '/dev/ttyUSB0' on Linux)
            baudrate: Communication baudrate (default: 9600)
        """
        # Initialize the XBee device
        self.device = XBeeDevice(port, baudrate)
        
        # Initialize variables
        self.temperature = 0.0
        self.humidity = 0.0
        self.ppm = 0.0
        self.last_received_time = 0
        
        # Flag to track if device is open
        self.is_open = False
        
        print("XBee API mode receiver initialized")
    
    def open(self):
        """Open the connection to the XBee device"""
        try:
            self.device.open()
            self.is_open = True
            print("XBee device opened successfully")
            
            # Configure the device to receive data
            self.device.add_data_received_callback(self._data_received_callback)
            
            return True
            
        except XBeeException as e:
            print(f"Error opening XBee device: {e}")
            return False
    
    def _data_received_callback(self, xbee_message):
        """
        Callback function that is called when data is received from an XBee device
        
        Args:
            xbee_message: The message received from the XBee network
        """
        
        # Declare last_sender as global variable
        global last_sender
        
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
            
    # Function to handle incoming data from XBee devices
    def data_received_old(xbee_message: XBeeMessage) -> None:
        """
        Callback when data is received from an XBee device.
        Prints the data with timestamp and sender information.
        """
        # Declare last_sender as global variable 
        global last_sender
        
        # Get current timestamp
        timestamp = date_time()
        
        # Get the sender's address
        #sender = xbee_message.remote_device.get_64bit_addr()
        # add class type to make linter happy
        sender: XBee64BitAddress = xbee_message.remote_device.get_64bit_addr()
        
        # Store the sender address if you want to log it
        last_sender = sender  
        
        # Get message and decode the data
        # use try except to handle decoding errors
        try:
            data = xbee_message.data.decode('utf-8')
            
        except UnicodeDecodeError:
            # If data can't be decoded as UTF-8 show it as hexadecimal
            # This will never get used but it is good practice to handle errors
            data = xbee_message.data.hex()
            data = ' '.join(data[i:i+2] for i in range(0, len(data), 2))
            data = f"(hex) {data}"
        
        # Print with timestamp and sender info
        print(f"[{timestamp}] From {sender}: {data}")
    
    def parse_data_string(self, data_string):
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
    
    def update(self):
        """
        Manual update method for non-callback operation
        Tries to read and process a message directly
        
        Returns True if new data was received and parsed successfully
        """
        if not self.is_open:
            if not self.open():
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
    
    def continuous_monitoring(self, check_interval=1):
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
    
    def close(self):
        """Close the XBee device connection"""
        if self.is_open:
            # Remove the callback
            self.device.del_data_received_callback(self._data_received_callback)
            
            # Close the device
            self.device.close()
            self.is_open = False
            print("XBee device closed")

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
        # Start continuous monitoring
        receiver.continuous_monitoring()
        
    except KeyboardInterrupt:
        print("\nScript terminated by user")
        
    finally:
        # Clean up resources
        receiver.close()

if __name__ == '__main__':
    main()
