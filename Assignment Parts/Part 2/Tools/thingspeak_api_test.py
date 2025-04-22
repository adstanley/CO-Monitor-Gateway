"""
ThingSpeak Test Script
Tests the ThingSpeakClient class to ensure it can connect and write to a ThingSpeak channel.
"""

import time
import random
import thingspeak

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
        
        # ThingSpeak limits free accounts to 15 seconds between updates
        self.min_interval = 15
        
        print(f"ThingSpeak client initialized for channel {channel_id}")
    
    def send_data(self, temperature, temperature_F, humidity, ppm):
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
                'field3': ppm,
                'field4': temperature_F
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


def simulate_sensor_data():
    """
    Generate simulated sensor data
    
    Returns:
        tuple: (temperature, humidity, ppm)
    """
    temperature = round(random.uniform(20.0, 30.0), 1)  # Temperature between 20-30°C
    temperature_F = round(temperature * 9/5 + 32, 1)         # Convert to Fahrenheit
    humidity = round(random.uniform(30.0, 70.0), 1)     # Humidity between 30-70%
    ppm = round(random.uniform(400, 1500))              # CO2 ppm between 400-1500
    
    return temperature, temperature_F, humidity, ppm


def run_test(channel_id, write_api_key, num_updates=5):
    """
    Run a test of the ThingSpeakClient by sending simulated data
    
    Args:
        channel_id: ThingSpeak channel ID
        write_api_key: ThingSpeak Write API Key
        num_updates: Number of updates to send
    """
    print("Starting ThingSpeak Test")
    print("-----------------------")
    
    # Initialize the ThingSpeak client
    client = ThingSpeakClient(channel_id, write_api_key)
    
    # Send multiple updates
    for i in range(num_updates):
        print(f"\nUpdate {i+1}/{num_updates}")
        
        # Generate simulated data
        temperature, temperature_F, humidity, ppm = simulate_sensor_data()
        print(f"Simulated data: Temperature={temperature}°C, Humidity={humidity}%, CO2={ppm}ppm")
        
        # Send data to ThingSpeak
        result = client.send_data(temperature, temperature_F, humidity, ppm)
        
        if result:
            print(f"Test update {i+1} successful!")
        else:
            print(f"Test update {i+1} failed!")
    
    print("\nTest completed!")


if __name__ == "__main__":
    # ThingSpeak settings
    CHANNEL_ID = 2925773
    WRITE_API_KEY = "NN8PKRCJ2TM6NHI3"
    
    # Run the test
    run_test(CHANNEL_ID, WRITE_API_KEY)