#include "api.h"

const char* GuestbookAPI::DATA_PATH = "/data/guestbook.json";

GuestbookAPI::GuestbookAPI() : _maxEntries(100), _maxNameLen(32),
    _maxMsgLen(256), _rateLimitSec(60), _rateCount(0) {}

void GuestbookAPI::begin(int maxEntries, int maxNameLen, int maxMsgLen,
                         int rateLimitSec) {
    _maxEntries = maxEntries;
    _maxNameLen = maxNameLen;
    _maxMsgLen = maxMsgLen;
    _rateLimitSec = rateLimitSec;

    // Ensure data directory exists
    if (!LittleFS.exists("/data")) {
        LittleFS.mkdir("/data");
    }

    // Initialize guestbook file if it doesn't exist
    if (!LittleFS.exists(DATA_PATH)) {
        JsonDocument doc;
        doc["entries"] = doc.to<JsonArray>();
        doc["next_id"] = 1;
        _writeEntries(doc);
    }
}

void GuestbookAPI::registerRoutes(AsyncWebServer* server) {
    // GET /api/guestbook
    server->on("/api/guestbook", HTTP_GET,
        [this](AsyncWebServerRequest* request) {
            JsonDocument doc = _readEntries();
            JsonObject resp = doc.to<JsonObject>();

            String output;
            serializeJson(doc, output);
            request->send(200, "application/json", output);
        }
    );

    // POST /api/guestbook
    server->on("/api/guestbook", HTTP_POST,
        [](AsyncWebServerRequest* request) {
            // Body handler below does the work; this is needed for the signature
        },
        NULL,
        [this](AsyncWebServerRequest* request, uint8_t* data, size_t len,
               size_t index, size_t total) {
            // Rate limit check
            String remoteIP = request->client()->remoteIP().toString();
            if (_isRateLimited(remoteIP)) {
                JsonDocument resp;
                resp["ok"] = false;
                resp["error"] = "rate_limited";
                resp["retry_after"] = _rateLimitSec;
                String output;
                serializeJson(resp, output);
                request->send(429, "application/json", output);
                return;
            }

            JsonDocument body;
            deserializeJson(body, (char*)data, len);

            String name = body["name"] | "";
            String message = body["message"] | "";

            // Validate
            name = _sanitize(name, _maxNameLen);
            message = _sanitize(message, _maxMsgLen);

            if (name.length() == 0) {
                request->send(400, "application/json",
                    "{\"ok\":false,\"error\":\"validation\",\"message\":\"name is required\"}");
                return;
            }
            if (message.length() == 0) {
                request->send(400, "application/json",
                    "{\"ok\":false,\"error\":\"validation\",\"message\":\"message is required\"}");
                return;
            }

            // Add entry
            JsonDocument doc = _readEntries();
            int id = _nextId(doc);

            JsonArray entries = doc["entries"];

            // Drop oldest if at max
            while (entries.size() >= (size_t)_maxEntries) {
                entries.remove(0);
            }

            JsonObject entry = entries.add<JsonObject>();
            entry["id"] = id;
            entry["name"] = name;
            entry["message"] = message;
            entry["timestamp"] = (unsigned long)(millis() / 1000);

            doc["next_id"] = id + 1;
            _writeEntries(doc);

            _recordPost(remoteIP);

            JsonDocument resp;
            resp["ok"] = true;
            resp["id"] = id;
            String output;
            serializeJson(resp, output);
            request->send(201, "application/json", output);
        }
    );

    // DELETE /api/guestbook (clear all)
    server->on("/api/guestbook", HTTP_DELETE,
        [this](AsyncWebServerRequest* request) {
            JsonDocument doc;
            doc["entries"] = doc.to<JsonArray>();
            doc["next_id"] = 1;
            _writeEntries(doc);

            request->send(200, "application/json", "{\"ok\":true}");
        }
    );
}

bool GuestbookAPI::_isRateLimited(const String& remoteIP) {
    unsigned long now = millis();
    for (int i = 0; i < _rateCount; i++) {
        // Simple: compare by string since we don't have MAC easily
        // In practice we use IP as a proxy for device identity
        if (now - _rateTable[i].lastPost < (unsigned long)_rateLimitSec * 1000) {
            // Check if this is the same IP (stored in mac field as hash)
            uint32_t hash = 0;
            for (unsigned int c = 0; c < remoteIP.length(); c++) {
                hash = hash * 31 + remoteIP[c];
            }
            uint32_t stored;
            memcpy(&stored, _rateTable[i].mac, sizeof(stored));
            if (hash == stored) {
                return true;
            }
        }
    }
    return false;
}

void GuestbookAPI::_recordPost(const String& remoteIP) {
    uint32_t hash = 0;
    for (unsigned int c = 0; c < remoteIP.length(); c++) {
        hash = hash * 31 + remoteIP[c];
    }

    // Find existing or use next slot
    int slot = -1;
    for (int i = 0; i < _rateCount; i++) {
        uint32_t stored;
        memcpy(&stored, _rateTable[i].mac, sizeof(stored));
        if (hash == stored) {
            slot = i;
            break;
        }
    }
    if (slot < 0) {
        if (_rateCount < MAX_RATE_ENTRIES) {
            slot = _rateCount++;
        } else {
            // Evict oldest
            slot = 0;
            unsigned long oldest = _rateTable[0].lastPost;
            for (int i = 1; i < MAX_RATE_ENTRIES; i++) {
                if (_rateTable[i].lastPost < oldest) {
                    oldest = _rateTable[i].lastPost;
                    slot = i;
                }
            }
        }
    }

    memcpy(_rateTable[slot].mac, &hash, sizeof(hash));
    _rateTable[slot].lastPost = millis();
}

JsonDocument GuestbookAPI::_readEntries() {
    JsonDocument doc;
    File f = LittleFS.open(DATA_PATH, "r");
    if (f) {
        deserializeJson(doc, f);
        f.close();
    }
    if (!doc["entries"].is<JsonArray>()) {
        doc["entries"] = doc.to<JsonArray>();
        doc["next_id"] = 1;
    }
    return doc;
}

void GuestbookAPI::_writeEntries(const JsonDocument& doc) {
    File f = LittleFS.open(DATA_PATH, "w");
    if (f) {
        serializeJson(doc, f);
        f.close();
    }
}

String GuestbookAPI::_sanitize(const String& input, int maxLen) {
    String clean = input;
    clean.replace("<", "");
    clean.replace(">", "");
    clean.trim();
    if ((int)clean.length() > maxLen) {
        clean = clean.substring(0, maxLen);
    }
    return clean;
}

int GuestbookAPI::_nextId(const JsonDocument& doc) {
    return doc["next_id"] | 1;
}
