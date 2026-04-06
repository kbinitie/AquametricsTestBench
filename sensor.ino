#include <WiFi.h>
#include <WebServer.h>
#include <Arduino.h>
#include <DHT.h>

// ==============================
// Pin assignments
// ==============================
#define PIN_DHT11 33

// ADC input map used to derive the dashboard metrics.
// Adjust these assignments and calibration helpers below to match your hardware.
const int ADC_PINS[] = {32, 34, 35, 36, 39};
const char *ADC_NAMES[] = {"water_temp_adc", "turbidity_adc", "ph_adc", "gpio36_vp_aux", "gpio39_vn_aux"};
const int NUM_ADC_PINS = 5;

// ==============================
// DHT11
// ==============================
DHT dht(PIN_DHT11, DHT11);

// ==============================
// Access point config
// ==============================
const char *AP_SSID = "AquametricsTestBench";
const char *AP_PASSWORD = "aquametrics123";
IPAddress apIp(192, 168, 4, 1);
IPAddress apGateway(192, 168, 4, 1);
IPAddress apSubnet(255, 255, 255, 0);

WebServer server(80);

const unsigned long READ_INTERVAL_MS = 10000;
unsigned long lastReadTime = 0;

const float ADC_MAX = 4095.0;
const float ADC_VOLTAGE = 3.3;
const char *SENSOR_ID = "ESP32-A1";

// Water temperature defaults assume an LM35/TMP36-style analog temperature probe.
const float WATER_TEMP_OFFSET_V = 0.5;
const float WATER_TEMP_C_PER_VOLT = 100.0;

// pH defaults assume a probe conditioned near 2.5V at neutral pH.
const float PH_NEUTRAL_VOLTAGE = 2.5;
const float PH_PER_VOLT = -5.56;

String latestPayload = "{}";
bool hasSample = false;

float adcToVoltage(int rawValue) {
  return (rawValue / ADC_MAX) * ADC_VOLTAGE;
}

float clampFloat(float value, float minValue, float maxValue) {
  if (value < minValue) {
    return minValue;
  }
  if (value > maxValue) {
    return maxValue;
  }
  return value;
}

float calculateWaterTempC(float voltage) {
  float waterTempC = (voltage - WATER_TEMP_OFFSET_V) * WATER_TEMP_C_PER_VOLT;
  return clampFloat(waterTempC, -20.0, 80.0);
}

float calculateTurbidityNtu(float voltage) {
  // Common analog turbidity probes are often approximated with this polynomial.
  float turbidity = (-1120.4 * voltage * voltage) + (5742.3 * voltage) - 4352.9;
  return clampFloat(turbidity, 0.0, 3000.0);
}

float calculatePh(float voltage) {
  float ph = 7.0 + ((voltage - PH_NEUTRAL_VOLTAGE) * PH_PER_VOLT);
  return clampFloat(ph, 0.0, 14.0);
}

String buildPayload(float dhtTemp, float dhtHumidity, int adcValues[]) {
  float waterTempVoltage = adcToVoltage(adcValues[0]);
  float turbidityVoltage = adcToVoltage(adcValues[1]);
  float phVoltage = adcToVoltage(adcValues[2]);

  float ambientTempC = isnan(dhtTemp) ? calculateWaterTempC(waterTempVoltage) : dhtTemp;
  float waterTempC = calculateWaterTempC(waterTempVoltage);
  float turbidityNtu = calculateTurbidityNtu(turbidityVoltage);
  float phValue = calculatePh(phVoltage);

  String payload = "{";

  payload += "\"sensor_id\":\"" + String(SENSOR_ID) + "\",";
  payload += "\"timestamp_ms\":" + String(millis()) + ",";
  payload += "\"ambient_temp_c\":" + String(ambientTempC, 2) + ",";
  payload += "\"water_temp_c\":" + String(waterTempC, 2) + ",";
  payload += "\"turbidity_ntu\":" + String(turbidityNtu, 2) + ",";
  payload += "\"ph\":" + String(phValue, 2) + ",";

  if (!isnan(dhtTemp)) {
    payload += "\"dht11_temp_c\":" + String(dhtTemp, 2) + ",";
    payload += "\"dht11_humidity\":" + String(dhtHumidity, 2) + ",";
  } else {
    payload += "\"dht11_temp_c\":null,";
    payload += "\"dht11_humidity\":null,";
  }

  payload += "\"adc\":{";
  for (int i = 0; i < NUM_ADC_PINS; i++) {
    float voltage = (adcValues[i] / ADC_MAX) * ADC_VOLTAGE;
    payload += "\"" + String(ADC_NAMES[i]) + "\":{";
    payload += "\"raw\":" + String(adcValues[i]) + ",";
    payload += "\"voltage\":" + String(voltage, 4);
    payload += "}";
    if (i < NUM_ADC_PINS - 1) {
      payload += ",";
    }
  }
  payload += "},";
  payload += "\"water_temp_voltage\":" + String(waterTempVoltage, 4) + ",";
  payload += "\"turbidity_voltage\":" + String(turbidityVoltage, 4) + ",";
  payload += "\"ph_voltage\":" + String(phVoltage, 4);
  payload += "}";

  return payload;
}

void sendJson(int statusCode, const String &body) {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Cache-Control", "no-store");
  server.send(statusCode, "application/json", body);
}

void handleRoot() {
  String body = "{";
  body += "\"project\":\"AquametricsTestBench\",";
  body += "\"device\":\"ESP32\",";
  body += "\"ssid\":\"" + String(AP_SSID) + "\",";
  body += "\"ip\":\"" + WiFi.softAPIP().toString() + "\",";
  body += "\"data_endpoint\":\"/data\",";
  body += "\"status\":\"";
  body += hasSample ? "ready" : "warming_up";
  body += "\"}";
  sendJson(200, body);
}

void handleData() {
  if (!hasSample) {
    sendJson(503, "{\"status\":\"warming_up\",\"message\":\"No sample collected yet\"}");
    return;
  }

  sendJson(200, latestPayload);
}

void handleNotFound() {
  sendJson(404, "{\"error\":\"not_found\"}");
}

void setupAccessPoint() {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(apIp, apGateway, apSubnet);

  bool started = WiFi.softAP(AP_SSID, AP_PASSWORD);
  if (!started) {
    Serial.println("Failed to start AP. Restarting...");
    delay(1000);
    ESP.restart();
  }

  Serial.println("Access point started");
  Serial.print("SSID: ");
  Serial.println(AP_SSID);
  Serial.print("Password: ");
  Serial.println(AP_PASSWORD);
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());
}

void setupServer() {
  server.on("/", HTTP_GET, handleRoot);
  server.on("/data", HTTP_GET, handleData);
  server.onNotFound(handleNotFound);
  server.begin();

  Serial.println("HTTP server started");
  Serial.println("Open http://192.168.4.1/ or http://192.168.4.1/data");
}

void sampleSensors() {
  float dhtTemp = dht.readTemperature();
  float dhtHumidity = dht.readHumidity();

  int adcValues[NUM_ADC_PINS];
  for (int i = 0; i < NUM_ADC_PINS; i++) {
    adcValues[i] = analogRead(ADC_PINS[i]);
  }

  Serial.println("--- Sensor Readings ---");
  if (isnan(dhtTemp) || isnan(dhtHumidity)) {
    Serial.println("  DHT11: read FAILED");
  } else {
    Serial.printf("  DHT11 Temp : %.1f C\n", dhtTemp);
    Serial.printf("  DHT11 Hum  : %.1f %%\n", dhtHumidity);
  }

  float waterTempVoltage = adcToVoltage(adcValues[0]);
  float turbidityVoltage = adcToVoltage(adcValues[1]);
  float phVoltage = adcToVoltage(adcValues[2]);
  float derivedAmbientTempC = isnan(dhtTemp) ? calculateWaterTempC(waterTempVoltage) : dhtTemp;
  float derivedWaterTempC = calculateWaterTempC(waterTempVoltage);
  float derivedTurbidityNtu = calculateTurbidityNtu(turbidityVoltage);
  float derivedPh = calculatePh(phVoltage);

  for (int i = 0; i < NUM_ADC_PINS; i++) {
    float voltage = adcToVoltage(adcValues[i]);
    Serial.printf("  %-10s : raw %4d, %.3fV\n", ADC_NAMES[i], adcValues[i], voltage);
  }

  Serial.println("  Derived Dashboard Metrics");
  Serial.printf("  Ambient Temp : %.2f C\n", derivedAmbientTempC);
  Serial.printf("  Water Temp   : %.2f C\n", derivedWaterTempC);
  Serial.printf("  Turbidity    : %.2f NTU\n", derivedTurbidityNtu);
  Serial.printf("  pH           : %.2f\n", derivedPh);

  latestPayload = buildPayload(dhtTemp, dhtHumidity, adcValues);
  hasSample = true;

  Serial.println("DATA: " + latestPayload);
}

// ==============================
// Setup
// ==============================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== ESP32 Sensor Node Starting ===");

  dht.begin();
  Serial.println("Waiting for DHT11 to stabilize...");
  delay(3000);

  setupAccessPoint();
  setupServer();
}

// ==============================
// Loop
// ==============================
void loop() {
  server.handleClient();

  unsigned long now = millis();
  if (now - lastReadTime >= READ_INTERVAL_MS) {
    lastReadTime = now;
    sampleSensors();
  }
}
