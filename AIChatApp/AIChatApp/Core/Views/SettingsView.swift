//
//  SettingsView.swift
//  AIChatApp
//
//  Created by İlhan Akbudak on 25.07.2025.
//

import SwiftUI

struct SettingsView: View {
    @AppStorage("apiBaseURL") private var apiBaseURL: String = ""

    var body: some View {
        Form {
            Section(header: Text("Server Configuration")) {
                TextField("API Base URL", text: $apiBaseURL)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .font(.body)
                    .disableAutocorrection(true)
            }

            Text("Example: http://127.0.0.1:8000")
                .font(.footnote)
                .foregroundColor(.secondary)
        }
        .padding()
        .navigationTitle("Settings")
    }
}
