#include "api.h"

const char* VisitorsAPI::DATA_PATH = "/data/visitors.json";

VisitorsAPI::VisitorsAPI() : _total(0), _current(0), _unflushed(0),
    _lastFlush(0) {}

void VisitorsAPI::begin() {
    if (!LittleFS.exists("/data")) {
        LittleFS.mkdir("/data");
    }
    _load();
    _lastFlush = millis();
}

void VisitorsAPI::registerRoutes(AsyncWebServer* server) {
    // GET /api/visitors
    server->on("/api/visitors", HTTP_GET,
        [this](AsyncWebServerRequest* request) {
            JsonDocument doc;
            doc["total"] = _total;
            doc["current"] = _current;
            String output;
            serializeJson(doc, output);
            request->send(200, "application/json", output);
        }
    );

    // POST /api/visitors/reset
    server->on("/api/visitors/reset", HTTP_POST,
        [this](AsyncWebServerRequest* request) {
            _total = 0;
            _current = 0;
            _unflushed = 0;
            _flush();

            request->send(200, "application/json", "{\"ok\":true}");
        }
    );
}

void VisitorsAPI::onClientConnect() {
    _current++;
    _total++;
    _unflushed++;

    // Flush every 10 new visitors
    if (_unflushed >= 10) {
        _flush();
    }
}

void VisitorsAPI::onClientDisconnect() {
    if (_current > 0) _current--;
}

void VisitorsAPI::loop() {
    // Flush every 5 minutes if there are unflushed changes
    if (_unflushed > 0 && millis() - _lastFlush > 300000) {
        _flush();
    }
}

void VisitorsAPI::_load() {
    if (!LittleFS.exists(DATA_PATH)) {
        _total = 0;
        return;
    }
    File f = LittleFS.open(DATA_PATH, "r");
    if (f) {
        JsonDocument doc;
        deserializeJson(doc, f);
        f.close();
        _total = doc["total"] | 0;
    }
}

void VisitorsAPI::_flush() {
    JsonDocument doc;
    doc["total"] = _total;
    File f = LittleFS.open(DATA_PATH, "w");
    if (f) {
        serializeJson(doc, f);
        f.close();
    }
    _unflushed = 0;
    _lastFlush = millis();
}
