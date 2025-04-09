#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>  

const char* ssid = "FasterThanYourEx";
const char* password = "Aapdu(1907)";
const char* serverName = "http://192.168.2.29:5000/sensor-data";

WebServer server(80);  // Create web server on port 80

String aiMessage = "";  // Store the latest AI message

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, 16, 17);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());  

  server.on("/send-ai-message", HTTP_POST, handleAiMessage);
  
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {

  server.handleClient();
  
  if (Serial2.available() > 0) {
    String sensorData = Serial2.readStringUntil('\n');
    sensorData.trim();

    if (sensorData.length() > 0) {
      Serial.println("Received from FRDM-K66F: " + sensorData);

      int comma1 = sensorData.indexOf(',');
      int comma2 = sensorData.indexOf(',', comma1 + 1);

      if (comma1 > 0 && comma2 > 0) {
      
      }
    }
  }
  
  if (aiMessage.length() > 0) {
    Serial2.println(aiMessage);
    Serial.println("Sent to FRDM-K66F: " + aiMessage);
    aiMessage = "";  
  }
  
  delay(10);
}

void handleAiMessage() {
  if (server.hasArg("plain")) {
    aiMessage = server.arg("plain");
    server.send(200, "text/plain", "Message received");
  } else {
    server.send(400, "text/plain", "No message received");
  }
}