//
//  ChatViewModel.swift
//  AIChatApp
//
//  Created by İlhan Akbudak on 25.07.2025.
//

import Foundation
import Combine
import SwiftUI

class ChatViewModel: NSObject, ObservableObject, URLSessionDataDelegate {
    @Published var messages: [ChatMessage] = []
    @Published var currentInput: String = ""
    @Published var streamingState: StreamingState = .idle
    @Published var isConnected: Bool = true
    
    @Published var scrollTrigger: UUID = UUID()
    
    @AppStorage("apiBaseURL") private var apiBaseURL: String = ""
    private var companyID: String = "my-company"

    private var streamingTask: URLSessionDataTask?
    private var currentStreamingMessage: ChatMessage?
    private var streamingMessageIndex: Int?
    private var streamBuffer: String = ""

    private var cancellables = Set<AnyCancellable>()

    private var session: URLSession!

    init(setup: Bool = true) {
        super.init()  // ✅ MUST be first

        let config = URLSessionConfiguration.default
        session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }


    func sendMessage(useStreaming: Bool = true) {
        let input = currentInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else { return }

        let userMessage = ChatMessage(isUser: true, text: input, timestamp: .now)
        messages.append(userMessage)

        if useStreaming {
            sendStreamingMessage(input)
        } else {
            sendNonStreamingMessage(input)
        }
    }

    private func sendStreamingMessage(_ message: String) {
        guard let url = URL(string: apiBaseURL + "/chat/stream") else {
            appendError("Invalid API URL")
            return
        }

        cancelCurrentStreaming()
        streamingState = .connecting

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")

        let body: [String: Any] = [
            "message": message,
            "company_id": companyID
        ]

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        } catch {
            appendError("Failed to create request")
            return
        }

        streamingTask = session.dataTask(with: request)
        streamingTask?.resume()
    }

    private func processStreamingData(_ data: Data) {
        guard let string = String(data: data, encoding: .utf8) else { return }

        streamBuffer += string
        let lines = streamBuffer.components(separatedBy: "\n")
        streamBuffer = lines.last ?? ""

        var currentEvent: String?
        var currentData: String?

        for line in lines.dropLast() {
            if line.hasPrefix("event: ") {
                currentEvent = String(line.dropFirst(7))
            } else if line.hasPrefix("data: ") {
                currentData = String(line.dropFirst(6))
            } else if line.isEmpty, let event = currentEvent, let data = currentData {
                handleSSEMessage(event: event, data: data)
                currentEvent = nil
                currentData = nil
            }
        }
    }

    private func handleSSEMessage(event: String, data: String) {
        switch event {
        case "status":
            handleStatusEvent(data)
        case "response_start":
            handleResponseStart(data)
        case "chunk":
            handleChunkEvent(data)
        case "response_complete":
            handleResponseComplete(data)
        case "warning":
            handleWarningEvent(data)
        case "error":
            handleErrorEvent(data)
        case "done":
            handleDoneEvent()
        default:
            print("Unknown SSE event: \(event)")
        }
    }

    private func handleStatusEvent(_ data: String) {
        if let eventData = parseEventData(data),
           let stage = eventData.stage {
            switch stage {
            case "retrieving_context":
                streamingState = .retrievingContext
            case "generating_response":
                streamingState = .generatingResponse
            default:
                break
            }
        }
    }

    private func handleResponseStart(_ data: String) {
        streamingState = .streaming

        let streamingMessage = ChatMessage(
            isUser: false,
            text: "",
            timestamp: .now,
            isStreaming: true,
            isComplete: false,
            streamingStatus: "responding..."
        )

        messages.append(streamingMessage)
        currentStreamingMessage = streamingMessage
        streamingMessageIndex = messages.count - 1
    }

    private func handleChunkEvent(_ data: String) {
        guard let eventData = parseEventData(data),
              let content = eventData.content,
              let messageIndex = streamingMessageIndex,
              messageIndex < messages.count else { return }

        var updatedMessage = messages[messageIndex]
        updatedMessage.text += content
        messages[messageIndex] = updatedMessage
        currentStreamingMessage = updatedMessage
        
        // Update this to trigger scroll
        scrollTrigger = UUID()
    }

    private func handleResponseComplete(_ data: String) {
        guard let messageIndex = streamingMessageIndex else { return }

        if let eventData = parseEventData(data),
           let fullResponse = eventData.fullResponse,
           messageIndex < messages.count {
            var updatedMessage = messages[messageIndex]
            updatedMessage.text = fullResponse
            updatedMessage.isStreaming = false
            updatedMessage.isComplete = true
            updatedMessage.streamingStatus = nil
            messages[messageIndex] = updatedMessage
        }

        streamingState = .completed

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            if self.streamingState == .completed {
                self.streamingState = .idle
            }
        }
    }

    private func handleWarningEvent(_ data: String) {
        if let eventData = parseEventData(data) {
            print("Warning: \(eventData.message ?? "Unknown warning")")
        }
    }

    private func handleErrorEvent(_ data: String) {
        if let eventData = parseEventData(data),
           let message = eventData.message {
            handleStreamingError(NSError(domain: "StreamingError", code: 0, userInfo: [NSLocalizedDescriptionKey: message]))
        }
    }

    private func handleDoneEvent() {
        finishStreaming()
    }

    private func parseEventData(_ data: String) -> StreamingEvent? {
        guard let jsonData = data.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(StreamingEvent.self, from: jsonData)
    }

    private func handleStreamingError(_ error: Error) {
        streamingState = .error(error.localizedDescription)

        if let messageIndex = streamingMessageIndex, messageIndex < messages.count {
            var updatedMessage = messages[messageIndex]
            if updatedMessage.text.isEmpty {
                updatedMessage.text = "[Error: \(error.localizedDescription)]"
            } else {
                updatedMessage.text += "\n[Connection interrupted]"
            }
            updatedMessage.isStreaming = false
            updatedMessage.isComplete = true
            updatedMessage.streamingStatus = nil
            messages[messageIndex] = updatedMessage
        } else {
            appendError(error.localizedDescription)
        }

        finishStreaming()
    }

    private func finishStreaming() {
        streamingTask?.cancel()
        streamingTask = nil
        currentStreamingMessage = nil
        streamingMessageIndex = nil
        streamBuffer = ""

        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            if case .error = self.streamingState {
                self.streamingState = .idle
            }
        }
    }

    private func cancelCurrentStreaming() {
        streamingTask?.cancel()
        streamingTask = nil

        if let messageIndex = streamingMessageIndex, messageIndex < messages.count {
            var updatedMessage = messages[messageIndex]
            if updatedMessage.isStreaming {
                updatedMessage.text += "\n[Interrupted]"
                updatedMessage.isStreaming = false
                updatedMessage.isComplete = true
                updatedMessage.streamingStatus = nil
                messages[messageIndex] = updatedMessage
            }
        }

        currentStreamingMessage = nil
        streamingMessageIndex = nil
        streamBuffer = ""
        streamingState = .idle
    }

    private func sendNonStreamingMessage(_ message: String) {
        guard let url = URL(string: apiBaseURL + "/chat/") else {
            appendError("Invalid API URL")
            return
        }

        streamingState = .generatingResponse

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "message": message,
            "company_id": companyID,
            "stream": false
        ]

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        } catch {
            appendError("Request serialization failed")
            return
        }

        URLSession.shared.dataTask(with: request) { data, _, error in
            DispatchQueue.main.async {
                self.streamingState = .idle

                if let error = error {
                    self.appendError(error.localizedDescription)
                    return
                }

                guard let data = data else {
                    self.appendError("No data from server.")
                    return
                }

                do {
                    if let response = try JSONSerialization.jsonObject(with: data) as? [String: String],
                       let reply = response["response"] {
                        let botMessage = ChatMessage(isUser: false, text: reply, timestamp: .now)
                        self.messages.append(botMessage)
                    } else {
                        self.appendError("Invalid server response.")
                    }
                } catch {
                    self.appendError("Response decode failed.")
                }
            }
        }.resume()
    }

    private func appendError(_ msg: String) {
        let err = ChatMessage(isUser: false, text: "[Error: \(msg)]", timestamp: .now)
        messages.append(err)
        streamingState = .idle
    }

    func stopStreaming() {
        cancelCurrentStreaming()
    }

    func clearMessages() {
        cancelCurrentStreaming()
        messages.removeAll()
    }

    func retryLastMessage() {
        guard let _ = messages.last(where: { $0.isUser }) else { return }

        messages.removeAll { !$0.isUser || $0.text.contains("[Error:") || $0.text.contains("[Interrupted]") }
        sendMessage(useStreaming: true)
    }
    
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        DispatchQueue.main.async {
            self.processStreamingData(data)
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        DispatchQueue.main.async {
            if let error = error {
                self.handleStreamingError(error)
            } else {
                self.handleDoneEvent()
            }
        }
    }
}
