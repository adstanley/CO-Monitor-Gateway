"""
XBee API Mode Receiver Script - Listen for incoming messages and display with timestamp
"""

import time
import datetime
from digi.xbee.devices import XBeeDevice, XBeeMessage
from digi.xbee.models.address import XBee64BitAddress

# Serial port settings
PORT = "COM4" 
BAUD_RATE = 9600

# Global variable to store the last sender address
last_sender = None

# Function to get the current date and time formatted as a string
def date_time() -> str:
    """
    Get the current date and time formatted as a string
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

class ThingSpeakClient:
    """Class for sending data to ThingSpeak API"""
    
    def __init__(self, api_key, server="api.thingspeak.com", use_ssl=False, wifi=None):
        """Initialize ThingSpeak client
        
        Args:
            api_key: ThingSpeak Write API Key
            server: ThingSpeak server address
            use_ssl: Whether to use HTTPS (True) or HTTP (False)
            wifi: Optional Wifi class instance to check connection
        """
        
        self.api_key = api_key
        self.server = server
        self.use_ssl = use_ssl
        self.wifi = wifi
        self.protocol = "https" if use_ssl else "http"
        self.port = 443 if use_ssl else 80
        self.last_connection_time = 0
        self.min_interval = 15  # ThingSpeak's minimum update interval in seconds
        
        # Import SSL module only if needed
        if use_ssl:
            import ssl
            self.ssl_context = ssl.create_default_context()
        
    def _create_request(self, fields):
        """Create HTTP request string for ThingSpeak update
        
        Args:
            fields: Dictionary of field_number -> value pairs
        
        Returns:
            HTTP request string
        """
        # Start with the base URL path
        url_path = f"/update?api_key={self.api_key}"
        
        # Add each field to the URL
        for field_num, value in fields.items():
            # Ensure field_num is an integer between 1 and 8
            if 1 <= field_num <= 8:
                # Format value as string with proper precision
                if isinstance(value, float):
                    # Format floats with 2 decimal places
                    formatted_value = f"{value:.2f}"
                else:
                    formatted_value = str(value)
                
                url_path += f"&field{field_num}={formatted_value}"
        
        # Create the HTTP request
        http_request = (
            f"GET {url_path} HTTP/1.1\r\n"
            f"Host: {self.server}\r\n"
            "Connection: close\r\n\r\n"
        )
        
        return http_request
    
    def send_data(self, temperature, humidity, ppm):
        """Send sensor data to ThingSpeak
        
        Args:
            temperature: Temperature reading
            humidity: Humidity reading
            ppm: CO2 PPM reading
            
        Returns:
            HTTP status code or error code
        """
        import socket
        import time
        
        # Check if we're respecting the rate limit
        current_time = time.time()
        if current_time - self.last_connection_time < self.min_interval:
            # Calculate remaining wait time
            wait_time = self.min_interval - (current_time - self.last_connection_time)
            print(f"Rate limit: waiting {wait_time:.1f} seconds before sending")
            time.sleep(wait_time)
        
        # Check WiFi connection if available
        if self.wifi and not self.wifi.is_connected():
            print("WiFi not connected, attempting to reconnect...")
            if not self.wifi.reconnect_wifi():
                print("Failed to reconnect WiFi, cannot send data")
                return -1
        
        # Prepare the data
        fields = {
            1: temperature,
            2: humidity,
            3: ppm
        }
        
        try:
            # Create socket
            s = socket.socket()
            
            # Set timeout to prevent hanging
            s.settimeout(10)
            
            print(f"Connecting to {self.server}...")
            
            # Connect to server
            addr = socket.getaddrinfo(self.server, self.port)[0][-1]
            s.connect(addr)
            
            # Wrap socket with SSL if needed
            if self.use_ssl:
                import ssl
                s = ssl.wrap_socket(s)
            
            # Create and send the request
            request = self._create_request(fields)
            print(f"Sending request: {request}")
            s.send(request.encode())
            
            # Get response
            response = b""
            while True:
                data = s.recv(100)
                if not data:
                    break
                response += data
            
            # Close socket
            s.close()
            
            # Parse response for status code
            response_str = response.decode()
            status_line = response_str.split("\r\n")[0]
            
            print(f"Response: {status_line}")
            
            # Extract status code
            try:
                status_code = int(status_line.split(" ")[1])
                # Update last connection time on success
                if 200 <= status_code < 300:
                    self.last_connection_time = time.time()
                    print("Data sent successfully")
                return status_code
            except (IndexError, ValueError):
                print("Failed to parse status code")
                return -2
            
        except OSError as e:
            print(f"Connection error: {e}")
            return -3
            
        except Exception as e:
            print(f"Error sending data: {e}")
            return -4
            
    def close(self):
        """Clean up resources"""
        # Nothing to close in this implementation
        pass

class APIReceiver:
    """Class for receiving and parsing sensor data from XBee in API mode"""
    
    # XBee API frame markers
    START_DELIMITER = 0x7E
    ESCAPE = 0x7D
    XON = 0x11
    XOFF = 0x13
    
    # API frame types
    RX_PACKET_64 = 0x80  # RX Packet: 64-bit address
    RX_PACKET_16 = 0x81  # RX Packet: 16-bit address
    RX_PACKET = 0x90     # Receive Packet
    
    def __init__(self, uart_id=0, baudrate=9600, tx_pin=4, rx_pin=5):
        """Initialize UART communication for XBee receiver in API mode"""
        self.uart = UART(uart_id, 
                       baudrate=baudrate, 
                       bits=8,
                       parity=None,
                       stop=1,
                       tx=tx_pin, 
                       rx=rx_pin,
                       timeout=1000)
        
        # Add small delay for XBee power up
        time.sleep(1)
        print("XBee API mode receiver initialized")
        
        # Initialize variables to store the parsed data
        self.temperature = 0.0
        self.humidity = 0.0
        self.ppm = 0.0
        self.last_received_time = 0
        
        # Buffer for incoming data
        self.buffer = bytearray()
    
    def _read_api_frame(self):
        """
        Read and parse an API frame from the UART
        Returns the frame data if a valid frame is found, None otherwise
        """
        # Check if there's data available
        if not self.uart.any():
            return None
        
        # Read available bytes into buffer
        new_data = self.uart.read()
        if new_data:
            self.buffer.extend(new_data)
        
        # Process buffer until we find a valid frame or run out of data
        while len(self.buffer) > 3:  # Minimum frame size (delimiter + 2 length bytes)
            # Look for start delimiter
            if self.buffer[0] != self.START_DELIMITER:
                # If first byte is not start delimiter, remove it and continue
                self.buffer.pop(0)
                continue
            
            # We have a potential frame start, check if we have enough bytes for length
            if len(self.buffer) < 3:
                # Not enough data yet, wait for more
                return None
            
            # Extract frame length (2 bytes, big endian)
            frame_length = (self.buffer[1] << 8) | self.buffer[2]
            
            # Check if we have the complete frame
            total_frame_size = frame_length + 4  # delimiter + 2 length bytes + data + checksum
            if len(self.buffer) < total_frame_size:
                # Not enough data yet, wait for more
                return None
            
            # We have a complete frame, extract it
            frame = self.buffer[:total_frame_size]
            
            # Remove the frame from the buffer
            self.buffer = self.buffer[total_frame_size:]
            
            # Verify checksum
            checksum = 0
            for i in range(3, total_frame_size - 1):
                checksum += frame[i]
            
            checksum = 0xFF - (checksum & 0xFF)
            
            if checksum != frame[-1]:
                print(f"Invalid checksum: calculated {checksum}, received {frame[-1]}")
                continue  # Discard invalid frame
            
            # Return the frame data (exclude delimiter, length, and checksum)
            return frame[3:total_frame_size-1]
        
        # No complete frame found
        return None
    
    def _unescape_data(self, data):
        """Unescape API data bytes"""
        result = bytearray()
        i = 0
        while i < len(data):
            if data[i] == self.ESCAPE:
                if i + 1 < len(data):
                    # XOR the next byte with 0x20
                    result.append(data[i+1] ^ 0x20)
                    i += 2
                else:
                    # Escape character at end of data (shouldn't happen)
                    i += 1
            else:
                result.append(data[i])
                i += 1
        return result
    
    def _process_rx_packet(self, frame_data):
        """
        Process a received API frame's data
        Returns the payload as a string if it's a valid RX packet
        """
        if not frame_data or len(frame_data) < 1:
            return None
        
        # Check frame type
        frame_type = frame_data[0]
        
        if frame_type == self.RX_PACKET:
            # API ID 0x90 - Receive Packet
            if len(frame_data) < 12:  # Minimum size for this frame type
                return None
            
            # Extract data from the frame
            # 64-bit source address (bytes 1-8)
            # 16-bit source network address (bytes 9-10)
            # Receive options (byte 11)
            # RF data (bytes 12+)
            rf_data = frame_data[12:]
            
            # Convert bytes to string
            try:
                return rf_data.decode('utf-8')
            except UnicodeError:
                print("Error decoding data")
                return None
                
        elif frame_type == self.RX_PACKET_16:
            # API ID 0x81 - Receive Packet, 16-bit address
            if len(frame_data) < 5:  # Minimum size for this frame type
                return None
                
            # Extract data from the frame
            # 16-bit source address (bytes 1-2)
            # RSSI (byte 3)
            # Options (byte 4)
            # RF data (bytes 5+)
            rf_data = frame_data[5:]
            
            # Convert bytes to string
            try:
                return rf_data.decode('utf-8')
            except UnicodeError:
                print("Error decoding data")
                return None
                
        elif frame_type == self.RX_PACKET_64:
            # API ID 0x80 - Receive Packet, 64-bit address
            if len(frame_data) < 11:  # Minimum size for this frame type
                return None
                
            # Extract data from the frame
            # 64-bit source address (bytes 1-8)
            # RSSI (byte 9)
            # Options (byte 10)
            # RF data (bytes 11+)
            rf_data = frame_data[11:]
            
            # Convert bytes to string
            try:
                return rf_data.decode('utf-8')
            except UnicodeError:
                print("Error decoding data")
                return None
        
        # Not a recognized RX packet type
        return None
    
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
        Read and process API frames, update stored values if valid data received
        Returns True if new data was received and parsed successfully
        """
        frame_data = self._read_api_frame()
        
        if frame_data:
            # Process the frame to extract RF data
            data_string = self._process_rx_packet(frame_data)
            
            if data_string:
                print(f"Received data: {data_string}")
                
                # Parse the data string
                result = self.parse_data_string(data_string)
                
                if result:
                    self.temperature, self.humidity, self.ppm = result
                    self.last_received_time = time.time()
                    return True
        
        return False
    
    def continuous_monitoring(self, check_interval=0.1):
        """
        Continuously monitor for incoming API frames
        
        Args:
            check_interval: Time between UART checks in seconds
        """
        print("Starting continuous API mode data reception...")
        try:
            while True:
                if self.update():
                    print("=========================================")
                    print("Received Sensor Data:")
                    print(f"Temperature: {self.temperature}°C")
                    print(f"Humidity: {self.humidity}%")
                    print(f"CO2 PPM: {self.ppm} ppm")
                    print("=========================================")
                
                # Small delay to prevent busy waiting
                # Shorter interval for API mode to catch frames more promptly
                time.sleep(check_interval)
                    
        except KeyboardInterrupt:
            print("Monitoring stopped")
            
        except Exception as e:
            print(f"Error during monitoring: {e}")
            raise e
            
        finally:
            self.close()
    
    def close(self):
        """Close UART connection"""
        self.uart.deinit()
        print("UART closed")



# Function to handle incoming data from XBee devices
def data_received(xbee_message: XBeeMessage) -> None:
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

def main():
    print("XBee API Mode Receiver")
    print(f"Device Located at serial port {PORT} at {BAUD_RATE} baud...")
    print(f"Device Serial Number: {XBeeDevice.get_serial_number(PORT)}")
    
    # Instantiate an XBee device object
    device = XBeeDevice(PORT, BAUD_RATE)
    
    try:
        # Open the device connection
        device.open()
        print(f"Connected to XBee on {PORT} at {BAUD_RATE} baud")
        
        # Get and print this device's 64-bit address
        my_address = device.get_64bit_addr()
        print(f"My XBee 64-bit address: {my_address}")
        
        # Define the data received callback
        device.add_data_received_callback(data_received)
        
        print("Listening for incoming transmissions... Press Ctrl+C to exit.")
        
        # Keep the main thread running indefinitely
        while True:
            time.sleep(5)  # Small delay to prevent CPU hogging
            
    except Exception as e:
        # If we encounter an error print it to the console
        print(f"Error: {e}")
        
    finally:
        # When we are done close the port
        if device and device.is_open():
            device.close()
            print("XBee connection closed")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript terminated by user")