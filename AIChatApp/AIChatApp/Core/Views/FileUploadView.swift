//
//  FileUploadView.swift
//  AIChatApp
//
//  Created by İlhan Akbudak on 25.07.2025.
//

import SwiftUI
import UniformTypeIdentifiers

struct FileUploadView: View {
    @StateObject private var viewModel = FileUploadViewModel()
    @EnvironmentObject var connectionStatus: ConnectionStatusManager
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header with connection status
            HStack {
                VStack(alignment: .leading) {
                    Text("Document Upload")
                        .font(.title2)
                        .fontWeight(.semibold)
                    
                    Text("Upload and process documents for AI chat")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                // Connection status indicator
                HStack(spacing: 8) {
                    Image(systemName: connectionStatus.status.icon)
                        .foregroundColor(connectionStatus.status.color)
                    
                    Text(connectionStatus.status.displayText)
                        .font(.caption)
                        .foregroundColor(connectionStatus.status.color)
                    
                    Button(action: connectionStatus.checkConnection) {
                        Image(systemName: "arrow.clockwise")
                            .font(.caption)
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
            
            Divider()
            
            // Upload section
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Button(action: selectFile) {
                        HStack {
                            Image(systemName: "plus.circle.fill")
                            Text("Choose File to Upload")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(Color.accentColor)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    }
                    .buttonStyle(PlainButtonStyle())
                    .disabled(viewModel.isUploading || viewModel.connectionStatus == .disconnected)
                    
                    if viewModel.isUploading {
                        ProgressView()
                            .scaleEffect(0.8)
                            .frame(width: 20, height: 20)
                        Text("Processing...")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                // System info display
                if let systemInfo = viewModel.systemInfo {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Upload Limits:")
                            .font(.caption)
                            .fontWeight(.medium)
                        
                        HStack {
                            Text("Max file size: \(systemInfo.settings.maxFileSizeMB)MB")
                            Spacer()
                            Text("Supported: \(systemInfo.settings.supportedFileTypes.joined(separator: ", "))")
                        }
                        .font(.caption)
                        .foregroundColor(.secondary)
                    }
                    .padding(8)
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(6)
                }
                
                // Result message
                if !viewModel.resultMessage.isEmpty {
                    Text(viewModel.resultMessage)
                        .font(.callout)
                        .padding(10)
                        .background(messageBackgroundColor)
                        .cornerRadius(8)
                        .foregroundColor(messageTextColor)
                }
            }
            
            Divider()
            
            // Files section
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Uploaded Documents")
                        .font(.headline)
                    
                    Spacer()
                    
                    if viewModel.isLoadingFiles {
                        ProgressView()
                            .scaleEffect(0.7)
                            .frame(width: 16, height: 16)
                    } else {
                        Text("\(viewModel.uploadedFiles.count) files")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                if viewModel.uploadedFiles.isEmpty {
                    VStack(spacing: 8) {
                        Image(systemName: "doc.text")
                            .font(.system(size: 40))
                            .foregroundColor(.gray)
                        
                        Text("No documents uploaded yet")
                            .font(.callout)
                            .foregroundColor(.secondary)
                        
                        Text("Upload documents to start chatting with your AI assistant")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 24)
                } else {
                    ScrollView {
                        LazyVStack(spacing: 8) {
                            ForEach(viewModel.uploadedFiles) { file in
                                FileRowView(file: file, onDelete: {
                                    viewModel.deleteFile(file)
                                })
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
            
            Spacer()
        }
        .padding()
        .navigationTitle("Upload")
    }
    
    // MARK: - Computed Properties
    private var messageBackgroundColor: Color {
        if viewModel.resultMessage.contains("✅") {
            return Color.green.opacity(0.2)
        } else if viewModel.resultMessage.contains("⚠️") {
            return Color.orange.opacity(0.2)
        } else if viewModel.resultMessage.contains("failed") || viewModel.resultMessage.contains("error") {
            return Color.red.opacity(0.2)
        } else {
            return Color.blue.opacity(0.2)
        }
    }
    
    private var messageTextColor: Color {
        if viewModel.resultMessage.contains("✅") {
            return Color.green
        } else if viewModel.resultMessage.contains("⚠️") {
            return Color.orange
        } else if viewModel.resultMessage.contains("failed") || viewModel.resultMessage.contains("error") {
            return Color.red
        } else {
            return Color.blue
        }
    }
    
    // MARK: - Actions
    private func selectFile() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [
            UTType.pdf,
            UTType.plainText,
            UTType(filenameExtension: "docx")!
        ]
        
        if panel.runModal() == .OK, let url = panel.url {
            viewModel.uploadFile(url)
        }
    }
}

// MARK: - File Row View
struct FileRowView: View {
    let file: UploadedFile
    let onDelete: () -> Void
    
    var body: some View {
        HStack(spacing: 12) {
            // File icon and status
            VStack {
                Image(systemName: fileIcon)
                    .font(.title2)
                    .foregroundColor(statusColor)
                
                Text(statusText)
                    .font(.caption2)
                    .foregroundColor(statusColor)
            }
            .frame(width: 50)
            
            // File details
            VStack(alignment: .leading, spacing: 4) {
                Text(file.filename)
                    .font(.callout)
                    .fontWeight(.medium)
                    .lineLimit(1)
                
                HStack {
                    if let sizeBytes = file.fileSizeBytes {
                        Text(formatFileSize(sizeBytes))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    if let chunks = file.chunksStored {
                        Text("• \(chunks) chunks")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                if let processingInfo = file.processingInfo {
                    Text(processingInfo)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
                
                Text("Uploaded: \(formatDate(file.uploadDate))")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            // Actions
            VStack {
                Button(action: onDelete) {
                    Image(systemName: "trash")
                        .foregroundColor(.red)
                }
                .buttonStyle(PlainButtonStyle())
                .help("Delete document")
            }
        }
        .padding(12)
        .background(rowBackgroundColor)
        .cornerRadius(8)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(borderColor, lineWidth: 1)
        )
    }
    
    // MARK: - Computed Properties
    private var fileIcon: String {
        let ext = (file.filename as NSString).pathExtension.lowercased()
        switch ext {
        case "pdf": return "doc.richtext"
        case "docx", "doc": return "doc.text"
        case "txt": return "doc.plaintext"
        default: return "doc"
        }
    }
    
    private var statusColor: Color {
        switch file.status {
        case .uploaded: return .green
        case .duplicate: return .orange
        case .failed: return .red
        case .uploading: return .blue
        }
    }
    
    private var statusText: String {
        switch file.status {
        case .uploaded: return "Ready"
        case .duplicate: return "Duplicate"
        case .failed: return "Failed"
        case .uploading: return "Processing"
        }
    }
    
    private var rowBackgroundColor: Color {
        switch file.status {
        case .uploaded: return Color(.controlBackgroundColor)
        case .duplicate: return Color.orange.opacity(0.1)
        case .failed: return Color.red.opacity(0.1)
        case .uploading: return Color.blue.opacity(0.1)
        }
    }
    
    private var borderColor: Color {
        switch file.status {
        case .uploaded: return Color.gray.opacity(0.3)
        case .duplicate: return Color.orange.opacity(0.5)
        case .failed: return Color.red.opacity(0.5)
        case .uploading: return Color.blue.opacity(0.5)
        }
    }
    
    // MARK: - Helper Functions
    private func formatFileSize(_ bytes: Int) -> String {
        let mb = Double(bytes) / (1024 * 1024)
        if mb < 1 {
            let kb = Double(bytes) / 1024
            return String(format: "%.0f KB", kb)
        } else {
            return String(format: "%.1f MB", mb)
        }
    }
    
    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

#Preview {
    FileUploadView()
}

