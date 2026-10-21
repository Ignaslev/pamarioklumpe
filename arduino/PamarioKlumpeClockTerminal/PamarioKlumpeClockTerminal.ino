#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#include <SPI.h>
#include <WiFiS3.h>

#include <MFRC522v2.h>
#include <MFRC522DriverSPI.h>
#include <MFRC522DriverPinSimple.h>
#include <MFRC522Debug.h>

#include "secrets.h"

const byte SELECT_PIN = 10;
const byte RESET_PIN = 9;
const unsigned long NORMAL_MESSAGE_MS = 3500UL;
const unsigned long UNASSIGNED_UID_MESSAGE_MS = 90000UL;

LiquidCrystal_I2C lcd(0x27, 16, 2);

MFRC522DriverPinSimple selectPin(SELECT_PIN);
const SPISettings readerSpiSettings(100000u, MSBFIRST, SPI_MODE0);
MFRC522DriverSPI driver(selectPin, SPI, readerSpiSettings);
MFRC522 tagReader(driver);

bool unassignedUidVisible = false;
unsigned long unassignedUidShownAt = 0;

void printLine(byte row, String text) {
  if (text.length() > 16) {
    text = text.substring(0, 16);
  }

  lcd.setCursor(0, row);
  lcd.print("                ");
  lcd.setCursor(0, row);
  lcd.print(text);
}

void showWaiting() {
  lcd.clear();
  printLine(0, "LAUKIAMA LUSTO");
  printLine(1, "PRIDEKITE LUSTA");
}

void resetTagReader() {
  pinMode(RESET_PIN, OUTPUT);
  digitalWrite(RESET_PIN, LOW);
  delay(30);

  // Release D9; the external 10k resistor pulls reset safely to 3.3V.
  pinMode(RESET_PIN, INPUT);
  delay(200);
}

void connectWiFi() {
  IPAddress noIp(0, 0, 0, 0);

  if (WiFi.status() == WL_CONNECTED && WiFi.localIP() != noIp) {
    return;
  }

  unassignedUidVisible = false;
  lcd.clear();
  printLine(0, "JUNGIAMASI WIFI");
  printLine(1, "PRASEME LAUKTI");

  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    WiFi.begin(CLOCK_WIFI_SSID, CLOCK_WIFI_PASSWORD);
    unsigned long startedAt = millis();

    while (WiFi.status() != WL_CONNECTED && millis() - startedAt < 10000UL) {
      delay(500);
      Serial.print(".");
    }
  }

  Serial.println();
  Serial.println("WiFi connected.");
  Serial.println("Waiting for IP...");

  lcd.clear();
  printLine(0, "WIFI PRISIJUNGE");
  printLine(1, "LAUKIAMA IP");

  while (WiFi.localIP() == noIp) {
    delay(500);
  }

  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  lcd.clear();
  printLine(0, "WIFI PARUOSTAS");
  printLine(1, WiFi.localIP().toString());
  delay(1200);
}

String getUid() {
  String uid = "";

  for (byte i = 0; i < tagReader.uid.size; i++) {
    if (tagReader.uid.uidByte[i] < 0x10) {
      uid += "0";
    }
    uid += String(tagReader.uid.uidByte[i], HEX);
  }

  uid.toUpperCase();
  return uid;
}

String jsonStringValue(const String &json, const char *key) {
  String keyMarker = String("\"") + key + "\"";
  int keyStart = json.indexOf(keyMarker);

  if (keyStart < 0) {
    return "";
  }

  int colon = json.indexOf(':', keyStart + keyMarker.length());
  int firstQuote = json.indexOf('"', colon + 1);

  if (colon < 0 || firstQuote < 0) {
    return "";
  }

  int lastQuote = json.indexOf('"', firstQuote + 1);

  if (lastQuote < 0) {
    return "";
  }

  return json.substring(firstQuote + 1, lastQuote);
}

bool jsonTrueValue(const String &json, const char *key) {
  String keyMarker = String("\"") + key + "\"";
  int keyStart = json.indexOf(keyMarker);

  if (keyStart < 0) {
    return false;
  }

  int colon = json.indexOf(':', keyStart + keyMarker.length());
  if (colon < 0) {
    return false;
  }

  String afterColon = json.substring(colon + 1);
  afterColon.trim();
  return afterColon.startsWith("true");
}

template <typename ClientType>
bool sendScanRequest(
  ClientType &client,
  const String &uid,
  int &statusCode,
  String &responseBody
) {
  statusCode = 0;
  responseBody = "";

  if (!client.connect(CLOCK_SERVER_HOST, CLOCK_SERVER_PORT)) {
    Serial.println("Could not connect to server.");
    return false;
  }

  String requestBody = String("{\"uid\":\"") + uid + "\"}";

  client.print("POST ");
  client.print(CLOCK_SERVER_PATH);
  client.println(" HTTP/1.1");

  client.print("Host: ");
  client.println(CLOCK_SERVER_HOST);
  client.println("Content-Type: application/json");

  client.print("X-Device-Key: ");
  client.println(CLOCK_DEVICE_KEY);

  client.print("Content-Length: ");
  client.println(requestBody.length());
  client.println("Connection: close");
  client.println();
  client.print(requestBody);
  client.setTimeout(6000);

  String statusLine = client.readStringUntil('\n');
  statusLine.trim();

  Serial.print("Server response: ");
  Serial.println(statusLine);

  if (statusLine.length() >= 12) {
    statusCode = statusLine.substring(9, 12).toInt();
  }

  while (client.connected()) {
    String header = client.readStringUntil('\n');
    if (header == "\r" || header.length() == 0) {
      break;
    }
  }

  unsigned long responseStartedAt = millis();
  while (millis() - responseStartedAt < 7000UL) {
    while (client.available()) {
      responseBody += (char)client.read();
    }

    if (!client.connected() && !client.available()) {
      break;
    }

    delay(10);
  }

  client.stop();

  Serial.print("Response body: ");
  Serial.println(responseBody);
  return true;
}

bool submitScan(const String &uid, int &statusCode, String &responseBody) {
  if (CLOCK_USE_HTTPS) {
    WiFiSSLClient client;
    return sendScanRequest(client, uid, statusCode, responseBody);
  }

  WiFiClient client;
  return sendScanRequest(client, uid, statusCode, responseBody);
}

bool showServerResult(int statusCode, const String &responseBody, const String &uid) {
  lcd.clear();

  if (statusCode == 200) {
    String worker = jsonStringValue(responseBody, "worker");
    String event = jsonStringValue(responseBody, "event");
    bool duplicate = jsonTrueValue(responseBody, "duplicate");

    printLine(0, worker.length() ? worker : "ZYMEJIMAS OK");

    if (duplicate) {
      printLine(1, "JAU PAZYMETA");
    } else if (event == "IN") {
      printLine(1, "ATVYKO");
    } else if (event == "OUT") {
      printLine(1, "ISVYKO");
    } else {
      printLine(1, "ZYMEJIMAS OK");
    }

    return false;
  }

  if (statusCode == 404) {
    printLine(0, "NEPRISK. LUSTAS");
    printLine(1, uid);
    return true;
  }

  if (statusCode == 401) {
    printLine(0, "RAKTO KLAIDA");
    printLine(1, "TIKRINK RAKTA");
    return false;
  }

  if (statusCode == 503) {
    printLine(0, "SERVERIS NEPAR.");
    printLine(1, "TIKRINK .ENV");
    return false;
  }

  printLine(0, "SERVERIO KLAIDA");
  printLine(1, "HTTP " + String(statusCode));
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Wire.begin();
  lcd.init();
  lcd.backlight();

  lcd.clear();
  printLine(0, "PAMARIO KLUMPE");
  printLine(1, "PALEIDZIAMA...");

  resetTagReader();
  tagReader.PCD_Init();

  Serial.println();
  Serial.println("Pamario Klumpe clock terminal");
  MFRC522Debug::PCD_DumpVersionToSerial(tagReader, Serial);

  connectWiFi();
  showWaiting();
}

void loop() {
  connectWiFi();

  if (unassignedUidVisible && millis() - unassignedUidShownAt >= UNASSIGNED_UID_MESSAGE_MS) {
    unassignedUidVisible = false;
    showWaiting();
  }

  if (!tagReader.PICC_IsNewCardPresent()) {
    delay(25);
    return;
  }

  unassignedUidVisible = false;

  if (!tagReader.PICC_ReadCardSerial()) {
    lcd.clear();
    printLine(0, "LUSTAS RASTAS");
    printLine(1, "SKAITYMO KLAIDA");
    delay(2000);
    showWaiting();
    return;
  }

  String uid = getUid();

  Serial.print("Tag UID: ");
  Serial.println(uid);

  lcd.clear();
  printLine(0, "UID:" + uid);
  printLine(1, "SIUNCIAMA...");
  delay(500);

  int statusCode = 0;
  String responseBody = "";
  bool connected = submitScan(uid, statusCode, responseBody);
  bool keepUnassignedUidVisible = false;

  if (!connected) {
    lcd.clear();
    printLine(0, "NERA RYSIO");
    printLine(1, "TIKRINK WIFI");
  } else {
    keepUnassignedUidVisible = showServerResult(statusCode, responseBody, uid);
  }

  tagReader.PICC_HaltA();
  tagReader.PCD_StopCrypto1();

  if (keepUnassignedUidVisible) {
    unassignedUidVisible = true;
    unassignedUidShownAt = millis();
    return;
  }

  delay(NORMAL_MESSAGE_MS);
  showWaiting();
}
