//
//  AIChatAppApp.swift
//  AIChatApp
//
//  Created by İlhan Akbudak on 25.07.2025.
//

import SwiftUI

// MARK: - Enhanced Sidebar System
enum SidebarItem: String, CaseIterable, Identifiable {
    case chat = "Chat"
    case upload = "Upload"
    case settings = "Settings"
    
    var id: String { self.rawValue }
    
    var icon: String {
        switch self {
        case .chat: return "bubble.left.and.bubble.right.fill"
        case .upload: return "square.and.arrow.up.on.square.fill"
        case .settings: return "gearshape.2.fill"
        }
    }
    
    var description: String {
        switch self {
        case .chat: return "Conversational AI assistant"
        case .upload: return "File management and processing"
        case .settings: return "App preferences and configuration"
        }
    }
    
    var accentColor: Color {
        switch self {
        case .chat: return .blue
        case .upload: return .green
        case .settings: return .orange
        }
    }
}

@main
struct AIChatAppApp: App {
    @State private var selectedItem: SidebarItem? = .chat
    @State private var isHovered: SidebarItem? = nil
    
    @State private var showAbout: Bool = false
    @StateObject private var connectionStatus = ConnectionStatusManager()
    
    @AppStorage("windowWidth") var windowWidth: Double = 960
    @AppStorage("windowHeight") var windowHeight: Double = 640
    @AppStorage("windowX") var windowX: Double = 0
    @AppStorage("windowY") var windowY: Double = 0

    
    var body: some Scene {
        WindowGroup {
            NavigationSplitView {
                ModernSidebarView(
                    selectedItem: $selectedItem,
                    hoveredItem: $isHovered,
                    showAbout: $showAbout
                )
                .environmentObject(connectionStatus)
                .navigationSplitViewColumnWidth(min: 260, ideal: 280, max: 300) // ✅ Sidebar size
            } detail: {
                Group {
                    switch selectedItem {
                    case .chat:
                        ChatView()
                    case .upload:
                        FileUploadView()
                    case .settings:
                        SettingsView()
                    case .none:
                        EmptyStateView()
                    }
                }
                .frame(minWidth: 480)
                .background(.ultraThinMaterial)
                .environmentObject(connectionStatus)
            }
            .background(
                WindowAccessor { window in
                    let savedFrame = NSRect(
                        x: windowX,
                        y: windowY,
                        width: windowWidth,
                        height: windowHeight
                    )
                    if !window.frame.equalTo(savedFrame) {
                        window.setFrame(savedFrame, display: true)
                    }

                    // Track window changes
                    NotificationCenter.default.addObserver(forName: NSWindow.didEndLiveResizeNotification, object: window, queue: .main) { _ in
                        let frame = window.frame
                        windowWidth = frame.width
                        windowHeight = frame.height
                        windowX = frame.origin.x
                        windowY = frame.origin.y
                    }
                }
            )
            .sheet(isPresented: $showAbout) {
                AboutView()
            }
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unifiedCompact)

    }
}

// MARK: - Modern Sidebar View
struct ModernSidebarView: View {
    @Binding var selectedItem: SidebarItem?
    @Binding var hoveredItem: SidebarItem?
    
    @Binding var showAbout: Bool
    
    var body: some View {
        VStack(spacing: 0) {
            // Enhanced Header
            SidebarHeaderView()
            
            // Elegant Divider
            Rectangle()
                .fill(
                    LinearGradient(
                        colors: [
                            Color(NSColor.separatorColor).opacity(0.3),
                            Color(NSColor.separatorColor),
                            Color(NSColor.separatorColor).opacity(0.3)
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .frame(height: 0.5)
            
            // Navigation Section
            VStack(spacing: 4) {
                // Section Header
                HStack {
                    Text("NAVIGATION")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.secondary)
                        .opacity(0.8)
                    Spacer()
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)
                .padding(.bottom, 8)
                
                
                // Navigation Items
                ForEach(SidebarItem.allCases) { item in
                    SidebarItemView(
                        item: item,
                        isSelected: selectedItem == item,
                        isHovered: hoveredItem == item,
                        onTap: { selectedItem = item },
                        onHover: { isHovering in
                            hoveredItem = isHovering ? item : nil
                        }
                    )
                }
                
                Spacer()
                

                SidebarFooterView(showAbout: $showAbout)
                
            }
            .padding(.horizontal, 8)
            .padding(.bottom, 12)
        }
        .frame(minWidth: 260, maxWidth: 300)
        .background(
            ZStack {
                // Base material
                Color(NSColor.controlBackgroundColor)
                
                // Subtle gradient overlay
                LinearGradient(
                    colors: [
                        Color.black.opacity(0.02),
                        Color.clear,
                        Color.white.opacity(0.03)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            }
        )
    }
}

// MARK: - Sidebar Header
struct SidebarHeaderView: View {
    
    var body: some View {
        HStack(spacing: 12) {
            // App Icon with enhanced styling
            ZStack {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [.blue.opacity(0.8), .purple.opacity(0.6)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 36, height: 36)
                    .shadow(color: .blue.opacity(0.3), radius: 8, x: 0, y: 2)
                
                Image(systemName: "sparkles")
                    .font(.title3)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
            }
            
            VStack(alignment: .leading, spacing: 2) {
                Text("AI Assistant")
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundColor(.primary)
                
                Text("Powered by Curiosity")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .opacity(0.8)
            }
            
            Spacer()
            
            
            
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 16)
        .background(.ultraThinMaterial)
    }
}

// MARK: - Sidebar Item
struct SidebarItemView: View {
    let item: SidebarItem
    let isSelected: Bool
    let isHovered: Bool
    let onTap: () -> Void
    let onHover: (Bool) -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                // Icon with dynamic styling
                ZStack {
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .fill(iconBackgroundColor)
                        .frame(width: 32, height: 32)
                    
                    Image(systemName: item.icon)
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(iconForegroundColor)
                }
                
                
                VStack(alignment: .leading, spacing: 2) {
                    Text(item.rawValue)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(textColor)
                    
                    Text(item.description)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
                
                Spacer()
                
                // Selection indicator
                if isSelected {
                    Circle()
                        .fill(item.accentColor)
                        .frame(width: 6, height: 6)
                }
                
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(backgroundStyle)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .scaleEffect(isHovered && !isSelected ? 1.02 : 1.0)
            .animation(.spring(response: 0.3, dampingFraction: 0.7), value: isHovered)
            .animation(.spring(response: 0.3, dampingFraction: 0.7), value: isSelected)
        }
        .buttonStyle(.plain)
        .onHover(perform: onHover)
        .help("")
    }
    
    private var backgroundStyle: some ShapeStyle {
        if isSelected {
            return AnyShapeStyle(
                LinearGradient(
                    colors: [
                        item.accentColor.opacity(0.15),
                        item.accentColor.opacity(0.08)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
        } else if isHovered {
            return AnyShapeStyle(.regularMaterial)
        } else {
            return AnyShapeStyle(Color.clear)
        }
    }
    
    private var iconBackgroundColor: Color {
        if isSelected {
            return item.accentColor.opacity(0.2)
        } else if isHovered {
            return Color(NSColor.controlColor).opacity(0.5)
        } else {
            return Color(NSColor.controlColor).opacity(0.3)
        }
    }
    
    private var iconForegroundColor: Color {
        if isSelected {
            return item.accentColor
        } else {
            return .primary
        }
    }
    
    private var textColor: Color {
        isSelected ? item.accentColor : .primary
    }
}

// MARK: - Sidebar Footer
struct SidebarFooterView: View {
    @EnvironmentObject var connectionStatus: ConnectionStatusManager
    @Binding var showAbout: Bool

    var body: some View {
        VStack(spacing: 12) {
            Divider().opacity(0.6)

            VStack(spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: connectionStatus.status.icon)
                        .foregroundColor(connectionStatus.status.color)
                        .font(.caption)
                    Text("Status: \(connectionStatus.status.displayText)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                }

                HStack {
                    Text("Version 0.0.1")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .opacity(0.7)

                    Spacer()

                    Button("About") {
                        showAbout = true
                    }
                    .font(.caption2)
                    .foregroundColor(.blue)
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 8)
        }
    }
}

// MARK: - Empty State View
struct EmptyStateView: View {
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 60))
                .foregroundStyle(.linearGradient(
                    colors: [.blue.opacity(0.6), .purple.opacity(0.4)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ))
            
            VStack(spacing: 8) {
                Text("Welcome to AI Assistant")
                    .font(.title2)
                    .fontWeight(.semibold)
                
                Text("Select a feature from the sidebar to get started")
                    .font(.body)
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(.regularMaterial)
    }
}


struct AboutView: View {
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("About This Project")
                .font(.title2)
                .fontWeight(.bold)

            Text("""
This is my open source side project. I'm exploring a highly customizable, no-code Retrieval-Augmented Generation (RAG) system for small enterprises.

The system is designed to serve as both a chatbot and call center backend. I plan to expand it further depending on available time and emerging technologies.

This macOS app serves as a testbed for backend capabilities.
""")
                .font(.body)
                .foregroundColor(.secondary)
            
            Spacer()
            
            HStack {
                Spacer()
                Button("Close") {
                    dismiss()
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding()
        .frame(minWidth: 420, idealWidth: 480, minHeight: 280)
    }
}
