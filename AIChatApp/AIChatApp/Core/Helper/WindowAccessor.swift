//
//  WindowAccessor.swift
//  AIChatApp
//
//  Created by İlhan Akbudak on 27.07.2025.
//

import AppKit
import SwiftUI

struct WindowAccessor: NSViewRepresentable {
    var onUpdate: (NSWindow) -> Void

    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        DispatchQueue.main.async {
            if let window = view.window {
                onUpdate(window)
            }
        }
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {}
}

