#ifndef WIFICITIES_CAPTIVE_PORTAL_H
#define WIFICITIES_CAPTIVE_PORTAL_H

#include <DNSServer.h>
#include <ESPAsyncWebServer.h>

class CaptivePortal {
public:
    CaptivePortal();

    // Start the DNS server that resolves all domains to our IP
    void beginDNS(const IPAddress& apIP);

    // Register captive portal detection routes on the web server
    void registerRoutes(AsyncWebServer* server, const IPAddress& apIP);

    // Must be called in loop() to process DNS requests
    void processDNS();

private:
    DNSServer _dnsServer;
    IPAddress _apIP;

    static void _handleAppleDetect(AsyncWebServerRequest* request, const IPAddress& ip);
    static void _handleAndroidDetect(AsyncWebServerRequest* request, const IPAddress& ip);
    static void _handleWindowsDetect(AsyncWebServerRequest* request, const IPAddress& ip);
};

#endif
