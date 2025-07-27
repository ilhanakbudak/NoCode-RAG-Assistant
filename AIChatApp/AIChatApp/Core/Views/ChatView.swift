//
//  ChatView.swift
//  AIChatApp
//
//  Created by İlhan Akbudak on 25.07.2025.
//

import SwiftUI

// MARK: - Modern Chat View
struct ChatView: View {
    @StateObject private var viewModel = ChatViewModel()
    @State private var useStreaming = true
    
    var body: some View {
        VStack(spacing: 0) {
            // Modern Header
            ChatHeaderView(
                streamingState: viewModel.streamingState,
                isStreaming: useStreaming,
                onToggleStreaming: { useStreaming.toggle() },
                onStopStreaming: { viewModel.stopStreaming() },
                onClearMessages: { viewModel.clearMessages() }
            )
            
            // Messages Area with Modern Styling
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 16) {
                        ForEach(viewModel.messages) { message in
                            MessageBubbleView(message: message)
                                .id(message.id)
                                .transition(.asymmetric(
                                    insertion: .opacity.combined(with: .move(edge: .bottom)),
                                    removal: .opacity.combined(with: .scale(scale: 0.8))
                                ))
                        }
                        
                        Color.clear
                            .frame(height: 20)
                            .id("bottom-anchor")
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 16)
                    .animation(.spring(response: 0.5, dampingFraction: 0.8), value: viewModel.messages.count)
                }
                .background(
                    // Subtle gradient background
                    LinearGradient(
                        colors: [
                            Color(NSColor.controlBackgroundColor),
                            Color(NSColor.controlBackgroundColor).opacity(0.95)
                        ],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .onChange(of: viewModel.messages.count) {
                    scrollToBottom(proxy: proxy)
                }
                .onChange(of: viewModel.streamingState) {
                    scrollToBottom(proxy: proxy)
                }
                .onChange(of: viewModel.scrollTrigger) {
                    scrollToBottom(proxy: proxy)
                }
            }
            
            // Modern Input Area
            ChatInputView(
                currentInput: $viewModel.currentInput,
                isStreaming: viewModel.streamingState.isActive,
                useStreaming: useStreaming,
                onSendMessage: {
                    viewModel.sendMessage(useStreaming: useStreaming)
                }
            )
        }
        .navigationTitle("")
        .background(.regularMaterial)
    }
    
    private func scrollToBottom(proxy: ScrollViewProxy) {
        withAnimation(.easeOut(duration: 0.6)) {
            proxy.scrollTo("bottom-anchor", anchor: .bottom)
        }
    }
}

// MARK: - Modern Chat Header
struct ChatHeaderView: View {
    let streamingState: StreamingState
    let isStreaming: Bool
    let onToggleStreaming: () -> Void
    let onStopStreaming: () -> Void
    let onClearMessages: () -> Void
    
    @EnvironmentObject var connectionStatus: ConnectionStatusManager
    
    var body: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Image(systemName: "brain.head.profile")
                        .font(.title2)
                        .foregroundStyle(.linearGradient(
                            colors: [.blue, .purple],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ))
                    
                    Text("Your Assistant")
                        .font(.title2)
                        .fontWeight(.semibold)
                }
                
                // Enhanced Status Indicator
                HStack(spacing: 8) {
                    ZStack {
                        Circle()
                            .fill(connectionStatus.status.color.opacity(0.2))
                            .frame(width: 12, height: 12)
                        
                        Circle()
                            .fill(connectionStatus.status.color)
                            .frame(width: 6, height: 6)
                            .scaleEffect(streamingState.isActive ? 1.3 : 1.0)
                            .animation(
                                streamingState.isActive
                                ? .easeInOut(duration: 1.0).repeatForever(autoreverses: true)
                                : .easeOut(duration: 0.3),
                                value: streamingState.isActive
                            )
                    }
                    
                    Text(statusText)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .fontWeight(.medium)
                }
            }
            
            Spacer()
            
            HStack(spacing: 12) {
                if streamingState.isActive {
                    Button(action: onStopStreaming) {
                        Image(systemName: "stop.circle.fill")
                            .font(.title2)
                            .foregroundStyle(.linearGradient(
                                colors: [.red, .orange],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ))
                    }
                    .buttonStyle(.plain)
                    .help("Stop current response")
                    .scaleEffect(1.0)
                    .animation(.spring(response: 0.3), value: streamingState.isActive)
                }
                
                Button(action: onToggleStreaming) {
                    HStack(spacing: 6) {
                        Image(systemName: isStreaming ? "bolt.fill" : "bolt.slash")
                            .font(.caption)
                        Text(isStreaming ? "Live" : "Standard")
                            .font(.caption)
                            .fontWeight(.semibold)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(isStreaming
                                  ? .linearGradient(
                                    colors: [.blue.opacity(0.8), .purple.opacity(0.6)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                  )
                                  : .linearGradient(
                                    colors: [.gray.opacity(0.3), .gray.opacity(0.2)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                  )
                                 )
                    )
                    .foregroundColor(isStreaming ? .white : .primary)
                }
                .buttonStyle(.plain)
                .help(isStreaming ? "Switch to standard mode" : "Switch to streaming mode")
                
                Button(action: onClearMessages) {
                    Image(systemName: "trash")
                        .font(.title3)
                        .foregroundColor(.secondary)
                        .padding(8)
                        .background(.ultraThinMaterial, in: Circle())
                }
                .buttonStyle(.plain)
                .help("Clear conversation")
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .background(.ultraThinMaterial)
        .overlay(
            Rectangle()
                .frame(height: 0.5)
                .foregroundColor(Color(NSColor.separatorColor)),
            alignment: .bottom
        )
    }
    
    private var statusText: String {
        // You can combine connection and streaming status here if desired
        if streamingState.isActive {
            return streamingState.displayText
        } else {
            return connectionStatus.status.displayText
        }
    }
}

// MARK: - Modern Message Bubble
struct MessageBubbleView: View {
    let message: ChatMessage
    
    var body: some View {
        HStack(alignment: .bottom, spacing: 12) {
            if message.isUser {
                Spacer(minLength: 60)
            } else {
                // AI Avatar
                Image(systemName: "sparkles")
                    .font(.caption)
                    .foregroundStyle(.linearGradient(
                        colors: [.blue, .purple],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ))
                    .frame(width: 28, height: 28)
                    .background(.ultraThinMaterial, in: Circle())
                    .overlay(Circle().stroke(Color(NSColor.separatorColor), lineWidth: 0.5))
            }
            
            VStack(alignment: message.isUser ? .trailing : .leading, spacing: 6) {
                // Message Bubble
                Text(message.text)
                    .font(.body)
                    .lineLimit(nil)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(messageBubbleBackground)
                    .foregroundColor(textColor)
                    .clipShape(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(bubbleStrokeColor, lineWidth: 0.5)
                    )
                    .shadow(
                        color: .black.opacity(0.05),
                        radius: 8,
                        x: 0,
                        y: 2
                    )
                
                // Message metadata
                HStack(spacing: 6) {
                    if !message.isUser && message.isStreaming {
                        HStack(spacing: 4) {
                            Text(message.streamingStatus ?? "Thinking...")
                                .font(.caption2)
                                .foregroundColor(.blue)
                                .fontWeight(.medium)
                        }
                    }
                    
                    Text(formatTime(message.timestamp))
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .fontWeight(.medium)
                }
                .padding(.horizontal, 4)
            }
            
            if !message.isUser {
                Spacer(minLength: 60)
            } else {
                // User Avatar placeholder
                Image(systemName: "person.crop.circle.fill")
                    .font(.title3)
                    .foregroundColor(.blue)
                    .frame(width: 28, height: 28)
            }
        }
    }
    
    private var messageBubbleBackground: some ShapeStyle {
        if message.isUser {
            return AnyShapeStyle(.linearGradient(
                colors: [.blue, .blue.opacity(0.8)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ))
        } else if message.isStreaming {
            return AnyShapeStyle(.linearGradient(
                colors: [.green.opacity(0.1), .blue.opacity(0.1)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ))
        } else {
            return AnyShapeStyle(.regularMaterial)
        }
    }
    
    private var bubbleStrokeColor: Color {
        if message.isUser {
            return .clear
        } else {
            return Color(NSColor.separatorColor).opacity(0.5)
        }
    }
    
    private var textColor: Color {
        message.isUser ? .white : .primary
    }
    
    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

// MARK: - Modern Chat Input
struct ChatInputView: View {
    @Binding var currentInput: String
    let isStreaming: Bool
    let useStreaming: Bool
    let onSendMessage: () -> Void
    
    @FocusState private var isInputFocused: Bool
    
    var body: some View {
        VStack(spacing: 0) {
            Rectangle()
                .frame(height: 0.5)
                .foregroundColor(Color(NSColor.separatorColor))
            
            HStack(spacing: 12) {
                // Modern input field
                HStack(spacing: 8) {
                    TextField("Ask me anything...", text: $currentInput, axis: .vertical)
                        .textFieldStyle(.plain)
                        .font(.body)
                        .focused($isInputFocused)
                        .disabled(isStreaming)
                        .lineLimit(1...6)
                        .onSubmit {
                            sendIfValid()
                        }
                    
                    // Modern send button
                    Button(action: sendIfValid) {
                        Image(systemName: isStreaming ? "stop.circle.fill" : "arrow.up.circle.fill")
                            .font(.largeTitle)
                            .foregroundStyle(
                                canSend
                                ? .linearGradient(
                                    colors: [.blue, .purple],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                                : .linearGradient(
                                    colors: [.gray.opacity(0.5), .gray.opacity(0.3)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                            .scaleEffect(canSend ? 1.0 : 0.9)
                            .animation(.spring(response: 0.3), value: canSend)
                    }
                    .buttonStyle(.plain)
                    .disabled(!canSend)
                    .keyboardShortcut(.defaultAction)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .stroke(isInputFocused ? .blue.opacity(0.5) : Color(NSColor.separatorColor), lineWidth: 1)
                )
                .animation(.easeInOut(duration: 0.2), value: isInputFocused)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 8)
            .background(.ultraThinMaterial)
        }
        .onAppear {
            isInputFocused = true
        }
    }
    
    private var canSend: Bool {
        !currentInput.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isStreaming
    }
    
    private func sendIfValid() {
        let trimmed = currentInput.trimmingCharacters(in: .whitespacesAndNewlines)
        if isStreaming {
            // Handle stop streaming
            return
        }
        if !trimmed.isEmpty {
            onSendMessage()
            currentInput = ""
            isInputFocused = true
        }
    }
}

