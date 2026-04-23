#include "api.h"

InfoAPI::InfoAPI() : _fwVersion("1.0.0") {}

void InfoAPI::begin(const String& siteName, const String& ssid,
                    const char* fwVersion) {
    _siteName = siteName;
    _ssid = ssid;
    _fwVersion = fwVersion;
}

void InfoAPI::registerRoutes(AsyncWebServer* server, VisitorsAPI* visitors) {
    server->on("/api/info", HTTP_GET,
        [this, visitors](AsyncWebServerRequest* request) {
            JsonDocument doc;
            doc["name"] = _siteName;
            doc["ssid"] = _ssid;
            doc["uptime"] = millis() / 1000;
            doc["version"] = _fwVersion;

            // Storage info
            size_t totalBytes = LittleFS.totalBytes();
            size_t usedBytes = LittleFS.usedBytes();
            JsonObject storage = doc["storage"].to<JsonObject>();
            storage["total"] = totalBytes;
            storage["used"] = usedBytes;
            storage["free"] = totalBytes - usedBytes;

            String output;
            serializeJson(doc, output);
            request->send(200, "application/json", output);
        }
    );
}
