#include <Arduino.h>
#include <WiFi.h>
#include <LittleFS.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>

#include "captive_portal.h"
#include "file_server.h"
#include "api.h"
#include "plugin_api.h"
#include "plugin_registry.h"

// ============================================================
// Version
// ============================================================
#define FIRMWARE_VERSION "1.0.0"

// ============================================================
// Defaults (used if config.json is missing or corrupt)
// ============================================================
#define DEFAULT_SSID       "WifiCity"
#define DEFAULT_PASSWORD   ""
#define DEFAULT_CHANNEL    1
#define DEFAULT_MAX_CONN   8
#define DEFAULT_GB_MAX     100
#define DEFAULT_GB_NAME_LEN 32
#define DEFAULT_GB_MSG_LEN  256
#define DEFAULT_GB_RATE     60

// ============================================================
// Global objects
// ============================================================
AsyncWebServer server(80);
CaptivePortal captivePortal;
FileServer fileServer;
GuestbookAPI guestbookAPI;
VisitorsAPI visitorsAPI;
InfoAPI infoAPI;
// Plugin storage pointers (for cleanup)
PluginStorage* pluginStorages[16];
int pluginStorageCount = 0;

// Config values
String cfgSSID;
String cfgPassword;
String cfgSiteName;
int cfgChannel;
int cfgMaxConnections;

// ============================================================
// WiFi event handler — track connects/disconnects
// ============================================================
void onWiFiEvent(WiFiEvent_t event) {
    switch (event) {
        case ARDUINO_EVENT_WIFI_AP_STACONNECTED:
            visitorsAPI.onClientConnect();
            // Notify plugins
            for (int i = 0; i < PLUGIN_COUNT; i++) {
                if (registered_plugins[i]->on_client_connect) {
                    registered_plugins[i]->on_client_connect("unknown");
                }
            }
            break;
        case ARDUINO_EVENT_WIFI_AP_STADISCONNECTED:
            visitorsAPI.onClientDisconnect();
            // Notify plugins
            for (int i = 0; i < PLUGIN_COUNT; i++) {
                if (registered_plugins[i]->on_client_disconnect) {
                    registered_plugins[i]->on_client_disconnect("unknown");
                }
            }
            break;
        default:
            break;
    }
}

// ============================================================
// Load config from LittleFS
// ============================================================
void loadConfig() {
    cfgSSID = DEFAULT_SSID;
    cfgPassword = DEFAULT_PASSWORD;
    cfgSiteName = DEFAULT_SSID;
    cfgChannel = DEFAULT_CHANNEL;
    cfgMaxConnections = DEFAULT_MAX_CONN;

    if (!LittleFS.exists("/config.json")) {
        Serial.println("[config] config.json not found, using defaults");
        return;
    }

    File f = LittleFS.open("/config.json", "r");
    if (!f) {
        Serial.println("[config] Failed to open config.json");
        return;
    }

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, f);
    f.close();

    if (err) {
        Serial.printf("[config] Parse error: %s, using defaults\n", err.c_str());
        return;
    }

    cfgSSID = doc["ssid"] | DEFAULT_SSID;
    cfgPassword = doc["password"] | DEFAULT_PASSWORD;
    cfgSiteName = doc["site_name"] | cfgSSID.c_str();
    cfgChannel = doc["channel"] | DEFAULT_CHANNEL;
    cfgMaxConnections = doc["max_connections"] | DEFAULT_MAX_CONN;

    // Guestbook config
    int gbMax = doc["guestbook_max_entries"] | DEFAULT_GB_MAX;
    int gbNameLen = doc["guestbook_max_name_length"] | DEFAULT_GB_NAME_LEN;
    int gbMsgLen = doc["guestbook_max_message_length"] | DEFAULT_GB_MSG_LEN;
    int gbRate = doc["guestbook_rate_limit_seconds"] | DEFAULT_GB_RATE;

    guestbookAPI.begin(gbMax, gbNameLen, gbMsgLen, gbRate);

    Serial.printf("[config] SSID: %s, Channel: %d, Max connections: %d\n",
                  cfgSSID.c_str(), cfgChannel, cfgMaxConnections);
}

// ============================================================
// Setup
// ============================================================
void setup() {
    Serial.begin(115200);
    Serial.println("\n\n=== WifiCities v" FIRMWARE_VERSION " ===\n");

    // 1. Initialize filesystem
    if (!LittleFS.begin(true)) {
        Serial.println("[fs] LittleFS mount failed!");
        return;
    }
    Serial.printf("[fs] LittleFS mounted. Total: %u bytes, Used: %u bytes\n",
                  LittleFS.totalBytes(), LittleFS.usedBytes());

    // Ensure data directory exists
    if (!LittleFS.exists("/data")) {
        LittleFS.mkdir("/data");
    }

    // 2. Load config
    loadConfig();

    // 3. Start WiFi AP
    WiFi.mode(WIFI_AP);
    WiFi.softAP(cfgSSID.c_str(),
                cfgPassword.length() > 0 ? cfgPassword.c_str() : NULL,
                cfgChannel, 0, cfgMaxConnections);

    IPAddress apIP = WiFi.softAPIP();
    Serial.printf("[wifi] AP started. SSID: %s, IP: %s\n",
                  cfgSSID.c_str(), apIP.toString().c_str());

    // Register WiFi event handler
    WiFi.onEvent(onWiFiEvent);

    // 4. Start DNS server (resolve all domains to our IP)
    captivePortal.beginDNS(apIP);
    Serial.println("[dns] DNS server started");

    // 5. Register captive portal detection routes
    captivePortal.registerRoutes(&server, apIP);
    Serial.println("[captive] Captive portal routes registered");

    // 6. Register built-in API routes
    guestbookAPI.registerRoutes(&server);
    Serial.println("[api] Guestbook API registered");

    visitorsAPI.begin();
    visitorsAPI.registerRoutes(&server);
    Serial.println("[api] Visitors API registered");

    infoAPI.begin(cfgSiteName, cfgSSID, FIRMWARE_VERSION);
    infoAPI.registerRoutes(&server, &visitorsAPI);
    Serial.println("[api] Info API registered");

    // 7. Initialize plugins
    if (PLUGIN_COUNT > 0) {
        // Re-read config for plugin sections
        JsonDocument configDoc;
        if (LittleFS.exists("/config.json")) {
            File f = LittleFS.open("/config.json", "r");
            if (f) {
                deserializeJson(configDoc, f);
                f.close();
            }
        }
        JsonObject pluginsConfig = configDoc["plugins"].as<JsonObject>();

        for (int i = 0; i < PLUGIN_COUNT; i++) {
            WifiCitiesPlugin* plugin = registered_plugins[i];
            Serial.printf("[plugin] Loading: %s v%s\n", plugin->name, plugin->version);

            // Create scoped server (enforces route prefix)
            ScopedServer* scoped = new ScopedServer(&server, plugin->api_prefix);

            // Create storage
            PluginStorage* storage = new PluginStorage(plugin->name);
            if (pluginStorageCount < 16) {
                pluginStorages[pluginStorageCount++] = storage;
            }

            // Register routes
            if (plugin->register_routes) {
                plugin->register_routes(scoped, storage);
            }

            // Get plugin config section
            JsonObject pConfig = pluginsConfig[plugin->name].as<JsonObject>();

            // Initialize
            if (plugin->on_init) {
                plugin->on_init(storage, pConfig);
            }

            Serial.printf("[plugin] %s loaded, routes at %s\n",
                          plugin->name, plugin->api_prefix);
        }
    }
    Serial.printf("[plugin] %d plugin(s) loaded\n", PLUGIN_COUNT);

    // 8. Register static file server (MUST be last — catch-all)
    fileServer.registerRoutes(&server);
    Serial.println("[fs] Static file server registered");

    // 9. Start web server
    server.begin();
    Serial.println("\n[ready] WifiCity is live!");
    Serial.printf("[ready] Connect to WiFi: %s\n", cfgSSID.c_str());
    Serial.printf("[ready] Then open: http://%s/\n", apIP.toString().c_str());
    Serial.println();
}

// ============================================================
// Loop
// ============================================================
void loop() {
    // Process DNS requests
    captivePortal.processDNS();

    // Flush visitor count if needed
    visitorsAPI.loop();

    // Auto-flush plugin storage
    for (int i = 0; i < pluginStorageCount; i++) {
        pluginStorages[i]->autoFlush();
    }

    delay(1);
}
