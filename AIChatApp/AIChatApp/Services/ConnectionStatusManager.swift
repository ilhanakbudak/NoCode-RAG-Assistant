//
//  ConnectionStatusManager.swift
//  AIChatApp
//
//  Created by İlhan Akbudak on 27.07.2025.
//

import Foundation
import SwiftUICore

class ConnectionStatusManager: ObservableObject {
    enum Status {
        case unknown, connected, disconnected, testing

        var displayText: String {
            switch self {
            case .unknown: return "Unknown"
            case .connected: return "Online"
            case .disconnected: return "Offline"
            case .testing: return "Checking..."
            }
        }

        var color: Color {
            switch self {
            case .unknown: return .gray
            case .connected: return .green
            case .disconnected: return .red
            case .testing: return .orange
            }
        }

        var icon: String {
            switch self {
            case .unknown: return "questionmark.circle"
            case .connected: return "checkmark.circle.fill"
            case .disconnected: return "xmark.circle.fill"
            case .testing: return "arrow.triangle.2.circlepath"
            }
        }
    }

    @Published var status: Status = .unknown

    init(autoCheck: Bool = true) {
        if autoCheck {
            checkConnection()
        }
    }

    func checkConnection() {
        status = .testing
        APIService.shared.testConnection { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success:
                    self?.status = .connected
                case .failure:
                    self?.status = .disconnected
                }
            }
        }
    }
}

