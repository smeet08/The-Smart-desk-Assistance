//Smeet Patel seneca polytechnic
//Arnav Nigam seneca polytechnic
#include "mbed.h"
#include "DHT.h"
#include "TEMT6000.h"
#include "LCDi2c.h"

// UART communication to ESP32
BufferedSerial esp32(PTC4, PTC3, 9600);  // TX, RX

// DHT11 Sensor
DHT dht(PTD2, DHT11);

// Light Sensor (TEMT6000)
TEMT6000 lightSensor(PTB7);

// I2C Interface for LCD Display
LCDi2c lcd(PTB3, PTB2, LCD16x2); // SDA, SCL

// Buzzer Pin
DigitalOut buzzer(PTC5);  // Active Buzzer connected to PTC5

// Prefix to detect AI break recommendation
const char breakPrefix[] = "BREAK:";

void displaySensorData(float temperature, float humidity, float lux) {
    lcd.cls();
    lcd.locate(0, 0);
    lcd.printf("T:%.1fC H:%.0f%%", temperature, humidity);
    lcd.locate(0, 1);
    lcd.printf("Lux: %.0f", lux);
}

void showAiNotification() {
    lcd.cls();
    lcd.locate(0, 0);
    lcd.printf("AI Suggestion");
    lcd.locate(0, 1);
    lcd.printf("Received!");

    buzzer = 1;
    thread_sleep_for(1000);  // Buzz for 1 second
    buzzer = 0;

    thread_sleep_for(2000);  // Show notification for ~2 more seconds
}

int main() {
    int error = 0;
    float temperature = 0.0f, humidity = 0.0f;
    float voltage = 0.0f, lux = 0.0f;
    char buffer[100] = {0};
    char response_buffer[200] = {0};

    lcd.cls();
    lcd.locate(0, 0);
    lcd.printf("Initializing...");
    thread_sleep_for(2000);

    while (1) {
        error = dht.readData();

        if (error == 0) {
            temperature = dht.ReadTemperature(CELCIUS);
            humidity = dht.ReadHumidity();
        }

        voltage = lightSensor.getVoltage();
        lux = (voltage * 1000) / 3.3;

        // Format and send sensor data
        sprintf(buffer, "%.2f,%.2f,%.0f\n", temperature, humidity, lux);
        esp32.write(buffer, sizeof("00.00,00.00,000\n"));

        // Read response from ESP32
        memset(response_buffer, 0, sizeof(response_buffer));
        int index = 0;
        while (esp32.readable() && index < sizeof(response_buffer) - 1) {
            char c;
            esp32.read(&c, 1);
            response_buffer[index++] = c;
            if (c == '\n') break;
        }
        response_buffer[index] = '\0';

        // Check if it's a break/AI message
        if (memcmp(response_buffer, breakPrefix, sizeof(breakPrefix) - 1) == 0) {
            showAiNotification();
        }

        // Show sensor data after AI notification or normally
        displaySensorData(temperature, humidity, lux);

        thread_sleep_for(1000);
    }
}
