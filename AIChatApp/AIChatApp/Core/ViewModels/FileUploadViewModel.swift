//
//  FileUploadViewModel.swift
//  AIChatApp
//
//  Created by İlhan Akbudak on 25.07.2025.
//

import Foundation
import SwiftUI

class FileUploadViewModel: ObservableObject {
    @Published var resultMessage: String = ""
    @Published var isUploading = false
    @Published var uploadedFiles: [UploadedFile] = []
    @Published var isLoadingFiles = false
    @Published var systemInfo: SystemInfoResponse?
    @Published var connectionStatus: ConnectionStatus = .unknown
    
    @AppStorage("apiBaseURL") private var apiBaseURL: String = "http://127.0.0.1:8000"
    private let companyID = "my-company"
    
    enum ConnectionStatus {
        case unknown, connected, disconnected, testing
        
        var displayText: String {
            switch self {
            case .unknown: return "Unknown"
            case .connected: return "Connected"
            case .disconnected: return "Disconnected"
            case .testing: return "Testing..."
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
    }
    
    init() {
        testConnection()
        loadServerFiles()
    }
    
    // MARK: - Connection Management
    func testConnection() {
        connectionStatus = .testing
        
        APIService.shared.testConnection { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success:
                    self?.connectionStatus = .connected
                    self?.loadSystemInfo()
                case .failure(let error):
                    self?.connectionStatus = .disconnected
                    self?.resultMessage = "Connection failed: \(error.localizedDescription)"
                }
            }
        }
    }
    
    private func loadSystemInfo() {
        APIService.shared.fetchSystemInfo { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let info):
                    self?.systemInfo = info
                case .failure(let error):
                    print("Failed to load system info: \(error.localizedDescription)")
                }
            }
        }
    }
    
    // MARK: - File Upload
    func uploadFile(_ url: URL) {
        isUploading = true
        resultMessage = "Preparing upload..."
        
        guard url.startAccessingSecurityScopedResource() else {
            isUploading = false
            resultMessage = "Upload failed: Unable to access file."
            return
        }
        
        defer { url.stopAccessingSecurityScopedResource() }
        
        // Pre-validate file
        do {
            let fileData = try Data(contentsOf: url)
            let fileSizeMB = Double(fileData.count) / (1024 * 1024)
            let maxSizeMB = systemInfo?.settings.maxFileSizeMB ?? 50
            
            if fileSizeMB > Double(maxSizeMB) {
                isUploading = false
                resultMessage = "File too large (\(String(format: "%.1f", fileSizeMB))MB). Maximum size: \(maxSizeMB)MB"
                return
            }
            
            let fileExtension = url.pathExtension.lowercased()
            let supportedTypes = systemInfo?.settings.supportedFileTypes ?? [".txt", ".pdf", ".docx"]
            
            if !supportedTypes.contains(".\(fileExtension)") {
                isUploading = false
                resultMessage = "Unsupported file type '.\(fileExtension)'. Supported: \(supportedTypes.joined(separator: ", "))"
                return
            }
            
        } catch {
            isUploading = false
            resultMessage = "Failed to read file: \(error.localizedDescription)"
            return
        }
        
        resultMessage = "Uploading and processing..."
        
        APIService.shared.uploadFile(url, companyID: companyID) { [weak self] result in
            DispatchQueue.main.async {
                self?.isUploading = false
                self?.handleUploadResult(result, filename: url.lastPathComponent)
            }
        }
    }
    
    private func handleUploadResult(_ result: Result<UploadResponse, Error>, filename: String) {
        switch result {
        case .success(let response):
            handleSuccessfulUpload(response, filename: filename)
        case .failure(let error):
            resultMessage = "Upload failed: \(error.localizedDescription)"
            
            // Add failed file to local list
            let failedFile = UploadedFile(
                id: UUID(),
                filename: filename,
                serverPath: "/upload/\(filename)",
                uploadDate: Date(),
                status: .failed,
                processingInfo: error.localizedDescription
            )
            uploadedFiles.append(failedFile)
            saveUploadedFiles()
        }
    }
    
    private func handleSuccessfulUpload(_ response: UploadResponse, filename: String) {
        let status: UploadStatus = response.status == "duplicate" ? .duplicate : .uploaded
        
        var processingInfo = ""
        if let chunksStored = response.chunksStored {
            processingInfo = "\(chunksStored) chunks stored"
            if let chunksSkipped = response.chunksSkipped, chunksSkipped > 0 {
                processingInfo += ", \(chunksSkipped) skipped"
            }
            
            // Add chunking method info
            if let settings = response.processingSettings {
                let method = settings.chunkingMethod ?? "basic"
                let docType = settings.documentType ?? "generic"
                processingInfo += " (\(method), \(docType))"
            }
        }
        
        let newFile = UploadedFile(
            id: UUID(),
            filename: filename,
            serverPath: "/upload/\(filename)",
            uploadDate: Date(),
            status: status,
            fileSizeBytes: response.fileSizeBytes,
            chunksStored: response.chunksStored,
            documentHash: response.documentHash,
            processingInfo: processingInfo
        )
        
        // Remove any existing file with same name
        uploadedFiles.removeAll { $0.filename == filename }
        uploadedFiles.append(newFile)
        saveUploadedFiles()
        
        // Update result message with enhanced info
        switch status {
        case .uploaded:
            resultMessage = "✅ \(response.message)"
            
            if let settings = response.processingSettings {
                resultMessage += "\nProcessed with \(settings.chunkingMethod ?? "basic") chunking"
                resultMessage += " (\(settings.chunkSize) chars, \(settings.chunkOverlap) overlap)"
            }
            
            if let stats = response.chunkingStatistics {
                resultMessage += "\nStatistics: \(stats.totalWords) words, \(stats.totalSentences) sentences"
                resultMessage += ", \(String(format: "%.1f", stats.avgWordsPerChunk)) avg words/chunk"
                
                // Show chunk type distribution
                let chunkTypeInfo = stats.chunkTypes.map { "\($0.key): \($0.value)" }.joined(separator: ", ")
                if !chunkTypeInfo.isEmpty {
                    resultMessage += "\nChunk types: \(chunkTypeInfo)"
                }
            }
            
        case .duplicate:
            resultMessage = "⚠️ \(response.message)"
            if let existingChunks = response.existingChunks {
                resultMessage += " (\(existingChunks) existing chunks)"
            }
        default:
            resultMessage = response.message
        }
        
        // Refresh server file list
        loadServerFiles()
    }
    
    // MARK: - File Management
    func loadServerFiles() {
        isLoadingFiles = true
        
        APIService.shared.fetchCompanyFiles(companyID: companyID) { [weak self] result in
            DispatchQueue.main.async {
                self?.isLoadingFiles = false
                self?.handleFileListResult(result)
            }
        }
    }
    
    private func handleFileListResult(_ result: Result<FileListResponse, Error>) {
        switch result {
        case .success(let response):
            // Convert server metadata to local file objects
            let serverFiles = response.documents.map { doc in
                UploadedFile(
                    id: UUID(),
                    filename: doc.filename,
                    serverPath: "/upload/\(doc.filename)",
                    uploadDate: doc.uploadDate,
                    status: .uploaded,
                    fileSizeBytes: doc.fileSizeBytes,
                    chunksStored: doc.chunksStored,
                    documentHash: doc.documentHash,
                    processingInfo: "\(doc.chunksStored) chunks, \(String(format: "%.1f", doc.fileSizeMB))MB"
                )
            }
            
            // Merge with local files, prioritizing server data
            var mergedFiles: [UploadedFile] = []
            
            // Add server files
            mergedFiles.append(contentsOf: serverFiles)
            
            // Add local files that aren't on server (failed uploads, etc.)
            for localFile in uploadedFiles {
                if !serverFiles.contains(where: { $0.filename == localFile.filename }) {
                    mergedFiles.append(localFile)
                }
            }
            
            uploadedFiles = mergedFiles.sorted { $0.uploadDate > $1.uploadDate }
            saveUploadedFiles()
            
        case .failure(let error):
            print("Failed to load server files: \(error.localizedDescription)")
            // Keep local files if server request fails
        }
    }
    
    func deleteFile(_ file: UploadedFile) {
        guard file.status == .uploaded || file.status == .duplicate else {
            // For failed uploads, just remove locally
            removeFileLocally(file)
            return
        }
        
        APIService.shared.deleteFile(filename: file.filename, companyID: companyID) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let response):
                    self?.resultMessage = "🗑️ \(response.filename) deleted (\(response.chunksDeleted) chunks removed)"
                    if let warning = response.warning {
                        self?.resultMessage += "\n⚠️ \(warning)"
                    }
                    self?.removeFileLocally(file)
                    self?.loadServerFiles() // Refresh list
                    
                case .failure(let error):
                    self?.resultMessage = "Delete failed: \(error.localizedDescription)"
                }
            }
        }
    }
    
    private func removeFileLocally(_ file: UploadedFile) {
        uploadedFiles.removeAll { $0.id == file.id }
        saveUploadedFiles()
    }
    
    // MARK: - Persistence
    private func saveUploadedFiles() {
        let url = getSavedFilePath()
        do {
            let data = try JSONEncoder().encode(uploadedFiles)
            try data.write(to: url)
        } catch {
            print("Failed to save uploaded file list: \(error)")
        }
    }
    
    private func loadUploadedFiles() {
        let url = getSavedFilePath()
        guard FileManager.default.fileExists(atPath: url.path) else { return }
        
        do {
            let data = try Data(contentsOf: url)
            uploadedFiles = try JSONDecoder().decode([UploadedFile].self, from: data)
        } catch {
            print("Failed to load uploaded file list: \(error)")
        }
    }
    
    private func getSavedFilePath() -> URL {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("uploaded_files.json")
    }
    
    // MARK: - Utility Functions
    func refreshData() {
        testConnection()
        loadServerFiles()
    }
    
    func getConnectionStatusIcon() -> String {
        switch connectionStatus {
        case .unknown: return "questionmark.circle"
        case .connected: return "checkmark.circle.fill"
        case .disconnected: return "xmark.circle.fill"
        case .testing: return "arrow.triangle.2.circlepath"
        }
    }
    
    func getFileSizeDisplay(_ sizeInBytes: Int?) -> String {
        guard let bytes = sizeInBytes else { return "Unknown size" }
        let mb = Double(bytes) / (1024 * 1024)
        return String(format: "%.1f MB", mb)
    }
}
