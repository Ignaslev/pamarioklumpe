#pragma once

// Copy this file to secrets.h and enter the real values there.
// secrets.h is ignored by Git and must never be committed.

#define CLOCK_WIFI_SSID "YOUR_WIFI_NAME"
#define CLOCK_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// Local test configuration:
#define CLOCK_SERVER_HOST "192.168.8.177"
#define CLOCK_DEVICE_KEY "PASTE_THE_SAME_KEY_USED_IN_DJANGO_ENV"
#define CLOCK_USE_HTTPS false
#define CLOCK_SERVER_PORT 8020
#define CLOCK_SERVER_PATH "/valdyti/api/clock/scan/"

// Restaurant/production configuration, for later:
// #define CLOCK_SERVER_HOST "valdyti.pamarioklumpe.lt"
// #define CLOCK_USE_HTTPS true
// #define CLOCK_SERVER_PORT 443
// #define CLOCK_SERVER_PATH "/api/clock/scan/"
