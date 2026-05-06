import serial

class ArduinoHandler:
    def __init__(self):
        self.set = serial.Serial('COM3', 9600)  # Adjust COM port and baud rate as needed

    def send_message(self, message : str):
        self.set.write((message + '\n').encode("utf-8"))  # Send the message to the Arduino
    
    def close(self):
        self.set.close()  # Close the serial connection when done
    
    