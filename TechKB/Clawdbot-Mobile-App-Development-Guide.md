# Building Clawdbot Mobile Apps: Complete Development Guide

*Last Updated: January 25, 2026*

## Overview

This guide covers how to build native macOS and iOS applications that integrate with **Clawdbot** - your personal AI assistant. Clawdbot uses a Gateway-based architecture where mobile apps connect as "nodes" via WebSocket to provide additional capabilities.

## 🏗️ Clawdbot Architecture

### Core Components

```
┌─────────────────────────────────────┐
│ WhatsApp/Telegram/Discord/iMessage  │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│ Gateway (Node.js)                   │
│ ws://127.0.0.1:18789                │
│ http://<host>:18793 (Canvas)        │
└─────────────┬───────────────────────┘
              │
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐
│macOS  │ │ iOS   │ │Android│
│ App   │ │ Node  │ │ Node  │
└───────┘ └───────┘ └───────┘
```

### Key Concepts

**Gateway:** Central hub running Node.js that manages all connections and agent communication
**Nodes:** Mobile/desktop apps that connect to Gateway via WebSocket to provide device-specific capabilities
**Canvas:** Web-based UI surface that nodes can render for interactive experiences
**Pairing:** Secure authentication process between nodes and Gateway

## 📱 Official Clawdbot Apps

### Available Apps
- **macOS App:** Menu bar companion with full Gateway management
- **iOS App:** Node app with Canvas, Camera, Screen capture (internal preview)
- **Android App:** Similar node capabilities to iOS
- **Web UI:** Browser-based control interface

### Source Code
- **Repository:** https://github.com/clawdbot/clawdbot
- **License:** MIT
- **Language:** Swift (iOS/macOS), TypeScript (Gateway), Node.js

## 🚀 Building Custom iOS Apps

### Prerequisites

```bash
# Development requirements
- Xcode 15+
- iOS 15+ deployment target
- Swift 5.9+
- WebSocket support
- Network framework access
```

### Core Architecture

#### 1. **WebSocket Connection to Gateway**

```swift
import Foundation
import Network

class ClawdbotGatewayClient {
    private var webSocketTask: URLSessionWebSocketTask?
    private let gatewayURL: URL
    
    init(gatewayHost: String = "127.0.0.1", port: Int = 18789) {
        self.gatewayURL = URL(string: "ws://\(gatewayHost):\(port)")!
    }
    
    func connect() {
        let session = URLSession(configuration: .default)
        webSocketTask = session.webSocketTask(with: gatewayURL)
        webSocketTask?.resume()
        
        // Start receiving messages
        receiveMessage()
    }
    
    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                self?.handleMessage(message)
                self?.receiveMessage() // Continue receiving
            case .failure(let error):
                print("WebSocket error: \(error)")
            }
        }
    }
    
    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        switch message {
        case .string(let text):
            print("Received: \(text)")
            // Parse and handle Gateway commands
        case .data(let data):
            print("Received data: \(data)")
        @unknown default:
            break
        }
    }
    
    func sendNodeStatus() {
        let status = [
            "type": "node.status",
            "nodeId": UIDevice.current.identifierForVendor?.uuidString ?? "unknown",
            "capabilities": ["canvas", "camera", "location"],
            "platform": "ios"
        ]
        
        if let data = try? JSONSerialization.data(withJSONObject: status),
           let json = String(data: data, encoding: .utf8) {
            webSocketTask?.send(.string(json)) { error in
                if let error = error {
                    print("Send error: \(error)")
                }
            }
        }
    }
}
```

#### 2. **Node Capabilities Implementation**

```swift
import UIKit
import WebKit

class ClawdbotNodeCapabilities {
    
    // MARK: - Canvas Implementation
    func setupCanvas() -> WKWebView {
        let webView = WKWebView()
        
        // Configure for Clawdbot Canvas
        let userScript = WKUserScript(
            source: """
                window.__clawdbot = {
                    ctx: null,
                    canvas: null
                };
                
                // Set up canvas when DOM loads
                document.addEventListener('DOMContentLoaded', function() {
                    const canvas = document.createElement('canvas');
                    canvas.width = window.innerWidth;
                    canvas.height = window.innerHeight;
                    canvas.style.position = 'fixed';
                    canvas.style.top = '0';
                    canvas.style.left = '0';
                    canvas.style.zIndex = '1000';
                    document.body.appendChild(canvas);
                    
                    window.__clawdbot.canvas = canvas;
                    window.__clawdbot.ctx = canvas.getContext('2d');
                });
            """,
            injectionTime: .atDocumentEnd,
            forMainFrameOnly: true
        )
        
        webView.configuration.userContentController.addUserScript(userScript)
        return webView
    }
    
    // MARK: - Camera Implementation
    func capturePhoto(completion: @escaping (Data?) -> Void) {
        let imagePickerController = UIImagePickerController()
        
        guard UIImagePickerController.isSourceTypeAvailable(.camera) else {
            completion(nil)
            return
        }
        
        imagePickerController.sourceType = .camera
        // Implementation details...
    }
    
    // MARK: - Location Implementation
    func getCurrentLocation(completion: @escaping (CLLocation?) -> Void) {
        // Core Location implementation
        // Return GPS coordinates for agent use
    }
    
    // MARK: - Screen Recording
    func startScreenRecording() {
        // ReplayKit implementation for screen capture
        // Available in iOS node capabilities
    }
}
```

#### 3. **Gateway Discovery & Pairing**

```swift
import Network

class ClawdbotDiscovery {
    private var browser: NWBrowser?
    
    func discoverGateways(completion: @escaping ([ClawdbotGateway]) -> Void) {
        // Bonjour service discovery
        let parameters = NWParameters()
        parameters.includePeerToPeer = true
        
        let descriptor = NWBrowser.Descriptor.bonjour(
            type: "_clawdbot._tcp",
            domain: "local."
        )
        
        browser = NWBrowser(for: descriptor, using: parameters)
        
        browser?.stateUpdateHandler = { state in
            switch state {
            case .ready:
                print("Browser ready")
            case .failed(let error):
                print("Browser failed: \(error)")
            default:
                break
            }
        }
        
        browser?.browseResultsChangedHandler = { results, changes in
            let gateways = results.compactMap { result -> ClawdbotGateway? in
                guard case let .service(name, type, domain, _) = result.endpoint else {
                    return nil
                }
                return ClawdbotGateway(
                    name: name,
                    host: result.endpoint.debugDescription,
                    port: 18789 // Default Gateway port
                )
            }
            completion(gateways)
        }
        
        browser?.start(queue: .main)
    }
    
    func pairWithGateway(_ gateway: ClawdbotGateway, 
                        completion: @escaping (Bool) -> Void) {
        // Send pairing request to Gateway
        let pairingRequest = [
            "type": "node.pair",
            "deviceName": UIDevice.current.name,
            "platform": "ios",
            "capabilities": ["canvas", "camera", "location", "screen"]
        ]
        
        // Send to gateway and handle response
        // Gateway will show approval prompt to user
    }
}

struct ClawdbotGateway {
    let name: String
    let host: String
    let port: Int
}
```

#### 4. **Command Processing**

```swift
struct ClawdbotCommand: Codable {
    let type: String
    let command: String
    let params: [String: Any]
    let requestId: String
}

class ClawdbotCommandProcessor {
    func processCommand(_ command: ClawdbotCommand) -> ClawdbotResponse {
        switch command.command {
        case "canvas.navigate":
            return handleCanvasNavigate(command.params)
        case "canvas.eval":
            return handleCanvasEval(command.params)
        case "canvas.snapshot":
            return handleCanvasSnapshot(command.params)
        case "camera.snap":
            return handleCameraSnap(command.params)
        case "location.get":
            return handleLocationGet(command.params)
        case "screen.record":
            return handleScreenRecord(command.params)
        default:
            return ClawdbotResponse(
                success: false,
                error: "Unknown command: \(command.command)"
            )
        }
    }
    
    private func handleCanvasNavigate(_ params: [String: Any]) -> ClawdbotResponse {
        guard let url = params["url"] as? String else {
            return ClawdbotResponse(success: false, error: "Missing URL")
        }
        
        // Navigate WebView to URL
        // Return success response
        return ClawdbotResponse(success: true, data: ["navigated": true])
    }
    
    private func handleCanvasSnapshot(_ params: [String: Any]) -> ClawdbotResponse {
        let maxWidth = params["maxWidth"] as? Int ?? 800
        let format = params["format"] as? String ?? "png"
        
        // Take screenshot of canvas WebView
        // Return base64 image data
        return ClawdbotResponse(
            success: true, 
            data: ["image": "base64ImageData", "format": format]
        )
    }
}

struct ClawdbotResponse: Codable {
    let success: Bool
    let error: String?
    let data: [String: Any]?
    
    init(success: Bool, error: String? = nil, data: [String: Any]? = nil) {
        self.success = success
        self.error = error
        self.data = data
    }
}
```

## 🖥️ Building Custom macOS Apps

### macOS App Architecture

The macOS app serves as both a Gateway manager and a node:

```swift
import Cocoa
import SwiftUI

@main
struct ClawdbotMacApp: App {
    @StateObject private var gatewayManager = GatewayManager()
    @StateObject private var nodeManager = NodeManager()
    
    var body: some Scene {
        MenuBarExtra("🦞", systemImage: "lobster") {
            MenuBarView()
                .environmentObject(gatewayManager)
                .environmentObject(nodeManager)
        }
        .menuBarExtraStyle(.window)
    }
}

class GatewayManager: ObservableObject {
    @Published var isRunning = false
    @Published var status = "Disconnected"
    
    func startLocalGateway() {
        // Launch Gateway via launchctl
        let task = Process()
        task.launchPath = "/usr/bin/launchctl"
        task.arguments = [
            "kickstart", "-k", 
            "gui/\(getuid())/com.clawdbot.gateway"
        ]
        task.launch()
    }
    
    func stopGateway() {
        let task = Process()
        task.launchPath = "/usr/bin/launchctl"
        task.arguments = [
            "bootout", 
            "gui/\(getuid())/com.clawdbot.gateway"
        ]
        task.launch()
    }
}
```

### macOS-Specific Capabilities

```swift
import ScreenCaptureKit
import AVFoundation

class MacOSNodeCapabilities {
    
    // MARK: - Screen Recording
    @available(macOS 12.3, *)
    func startScreenRecording(completion: @escaping (URL?) -> Void) {
        Task {
            do {
                let availableContent = try await SCShareableContent.excludingDesktopWindows(
                    false,
                    onScreenWindowsOnly: true
                )
                
                guard let display = availableContent.displays.first else {
                    completion(nil)
                    return
                }
                
                let filter = SCContentFilter(display: display, excludingWindows: [])
                let configuration = SCStreamConfiguration()
                
                // Configure recording settings
                configuration.width = Int(display.width)
                configuration.height = Int(display.height)
                configuration.pixelFormat = kCVPixelFormatType_32BGRA
                
                // Start recording and save to file
                // Return file URL
            } catch {
                print("Screen recording error: \(error)")
                completion(nil)
            }
        }
    }
    
    // MARK: - System Commands
    func executeSystemCommand(_ command: String) -> String {
        let task = Process()
        let pipe = Pipe()
        
        task.standardOutput = pipe
        task.standardError = pipe
        task.launchPath = "/bin/zsh"
        task.arguments = ["-c", command]
        
        task.launch()
        task.waitUntilExit()
        
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        return String(data: data, encoding: .utf8) ?? ""
    }
    
    // MARK: - Notifications
    func sendNotification(title: String, body: String) {
        let notification = NSUserNotification()
        notification.title = title
        notification.informativeText = body
        notification.deliveryDate = Date()
        
        NSUserNotificationCenter.default.deliver(notification)
    }
}
```

## 🔐 Security & Permissions

### iOS Permissions Required

```xml
<!-- Info.plist -->
<key>NSCameraUsageDescription</key>
<string>Clawdbot needs camera access for photo capture commands</string>

<key>NSLocationWhenInUseUsageDescription</key>
<string>Clawdbot needs location access for location-based commands</string>

<key>NSMicrophoneUsageDescription</key>
<string>Clawdbot needs microphone access for voice commands</string>

<key>NSLocalNetworkUsageDescription</key>
<string>Clawdbot needs local network access to connect to Gateway</string>
```

### macOS Permissions (TCC)

```swift
// Request screen recording permission
func requestScreenRecordingPermission() -> Bool {
    if #available(macOS 12.3, *) {
        return SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true) != nil
    }
    return false
}

// Request accessibility permission
func requestAccessibilityPermission() -> Bool {
    let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true]
    return AXIsProcessTrustedWithOptions(options as CFDictionary)
}
```

## 🚀 Development Setup

### Setting Up Development Environment

```bash
# 1. Clone Clawdbot repository
git clone https://github.com/clawdbot/clawdbot.git
cd clawdbot

# 2. Install dependencies
pnpm install

# 3. Build the Gateway
pnpm build

# 4. Start Gateway for development
clawdbot gateway --port 18789

# 5. Open iOS/macOS projects
# iOS: apps/ios/
# macOS: apps/macos/
```

### iOS Development

```bash
# Navigate to iOS app directory
cd apps/ios

# Open in Xcode
open ClawdbotNode.xcodeproj

# Or build from command line
swift build
swift run ClawdbotNode
```

### macOS Development

```bash
# Navigate to macOS app directory
cd apps/macos

# Build and run
swift build
swift run Clawdbot

# Package app bundle
scripts/package-mac-app.sh
```

## 📋 Example Project Structure

```
ClawdbotNode/
├── Sources/
│   ├── ClawdbotNode/
│   │   ├── main.swift
│   │   ├── GatewayClient.swift
│   │   ├── NodeCapabilities.swift
│   │   ├── CommandProcessor.swift
│   │   └── Discovery.swift
│   └── ClawdbotNodeUI/
│       ├── ContentView.swift
│       ├── SettingsView.swift
│       └── CanvasView.swift
├── Resources/
│   └── Info.plist
├── Package.swift
└── README.md
```

## 🛠️ Testing & Debugging

### Debug Commands

```bash
# Test Gateway connection from iOS app
swift run clawdbot-ios connect --json

# Discover available Gateways
swift run clawdbot-ios discover --timeout 3000 --json

# Test node commands
clawdbot nodes status
clawdbot nodes invoke --node "iOS Node" --command "canvas.snapshot"
```

### Common Issues

**Connection Issues:**
- Ensure Gateway is running on correct port
- Check firewall settings for WebSocket connections
- Verify network connectivity (same LAN or Tailnet)

**Pairing Problems:**
- Run `clawdbot nodes pending` to see pending requests
- Manually approve with `clawdbot nodes approve <requestId>`
- Check Keychain for stored pairing tokens

**Permission Errors:**
- Grant required iOS permissions in Settings
- For macOS, grant TCC permissions (Screen Recording, Accessibility)

## 📚 Resources & References

### Official Documentation
- [Clawdbot Docs](https://docs.clawd.bot)
- [GitHub Repository](https://github.com/clawdbot/clawdbot)
- [iOS Platform Guide](https://docs.clawd.bot/platforms/ios)
- [macOS Platform Guide](https://docs.clawd.bot/platforms/macos)

### Development Resources
- [Gateway Protocol](https://docs.clawd.bot/gateway/protocol)
- [Node Pairing](https://docs.clawd.bot/start/pairing)
- [Canvas Development](https://docs.clawd.bot/platforms/mac/canvas)
- [Security Guidelines](https://docs.clawd.bot/gateway/security)

### Community
- [GitHub Issues](https://github.com/clawdbot/clawdbot/issues)
- [Contributing Guide](https://github.com/clawdbot/clawdbot/blob/main/CONTRIBUTING.md)

## 💡 Pro Tips

1. **Start with the official apps** as reference implementation
2. **Use Bonjour discovery** for seamless Gateway detection
3. **Implement proper error handling** for network failures
4. **Cache pairing tokens** securely in Keychain
5. **Test on real devices** - some capabilities don't work in simulator
6. **Follow Apple's HIG** for native app feel
7. **Implement background modes** carefully - iOS suspends apps aggressively

## 🎯 Quick Start Checklist

**For iOS Development:**
- [ ] Clone Clawdbot repository
- [ ] Set up development Gateway
- [ ] Configure iOS project with required permissions
- [ ] Implement WebSocket connection to Gateway
- [ ] Add node capability handlers
- [ ] Test pairing and command processing
- [ ] Deploy to device for full testing

**For macOS Development:**
- [ ] Set up local Gateway with launchctl
- [ ] Request necessary TCC permissions
- [ ] Implement menu bar interface
- [ ] Add Gateway management controls
- [ ] Test system command execution
- [ ] Package as signed app bundle

---

*This guide covers Clawdbot mobile app development as of January 2025. Check the official documentation for the latest updates and API changes.*