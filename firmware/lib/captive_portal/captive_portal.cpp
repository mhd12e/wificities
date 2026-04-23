#include "captive_portal.h"

CaptivePortal::CaptivePortal() {}

void CaptivePortal::beginDNS(const IPAddress& apIP) {
    _apIP = apIP;
    // Resolve all DNS queries to our IP
    _dnsServer.start(53, "*", apIP);
}

void CaptivePortal::registerRoutes(AsyncWebServer* server, const IPAddress& apIP) {
    _apIP = apIP;
    String redirectURL = "http://" + apIP.toString() + "/";

    // iOS / macOS captive portal detection
    server->on("/hotspot-detect.html", HTTP_GET,
        [redirectURL](AsyncWebServerRequest* request) {
            request->redirect(redirectURL);
        }
    );

    // Android captive portal detection
    server->on("/generate_204", HTTP_GET,
        [redirectURL](AsyncWebServerRequest* request) {
            request->redirect(redirectURL);
        }
    );

    // Android alternate
    server->on("/gen_204", HTTP_GET,
        [redirectURL](AsyncWebServerRequest* request) {
            request->redirect(redirectURL);
        }
    );

    // Windows captive portal detection
    server->on("/connecttest.txt", HTTP_GET,
        [redirectURL](AsyncWebServerRequest* request) {
            request->redirect(redirectURL);
        }
    );

    // Windows alternate
    server->on("/ncsi.txt", HTTP_GET,
        [redirectURL](AsyncWebServerRequest* request) {
            request->redirect(redirectURL);
        }
    );

    // Samsung captive portal detection
    server->on("/check_network", HTTP_GET,
        [redirectURL](AsyncWebServerRequest* request) {
            request->redirect(redirectURL);
        }
    );

    // Firefox captive portal detection
    server->on("/canonical.html", HTTP_GET,
        [redirectURL](AsyncWebServerRequest* request) {
            request->redirect(redirectURL);
        }
    );

    // Generic fallback: redirect any request to a known captive portal domain
    server->on("/redirect", HTTP_GET,
        [redirectURL](AsyncWebServerRequest* request) {
            request->redirect(redirectURL);
        }
    );
}

void CaptivePortal::processDNS() {
    _dnsServer.processNextRequest();
}
