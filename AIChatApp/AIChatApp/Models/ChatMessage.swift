//
//  ChatMessage.swift
//  AIChatApp
//
//  Created by İlhan Akbudak on 25.07.2025.
//

import Foundation

// MARK: - Streaming Event Models
struct StreamingEvent: Codable {
    let type: String
    let message: String?
    let content: String?
    let chunkId: Int?
    let stage: String?
    let contextLength: Int?
    let fullResponse: String?
    let chunkCount: Int?
    let wordCount: Int?
    
    enum CodingKeys: String, CodingKey {
        case type, message, content, stage
        case chunkId = "chunk_id"
        case contextLength = "context_length"
        case fullResponse = "full_response"
        case chunkCount = "chunk_count"
        case wordCount = "word_count"
    }
}

// MARK: - Enhanced Chat Message
struct ChatMessage: Identifiable {
    let id = UUID()
    let isUser: Bool
    var text: String
    let timestamp: Date
    var isStreaming: Bool = false
    var isComplete: Bool = true
    var streamingStatus: String?
}

// MARK: - Streaming States
enum StreamingState: Equatable {
    case idle
    case connecting
    case retrievingContext
    case generatingResponse
    case streaming
    case completed
    case error(String)
    
    var isActive: Bool {
        switch self {
        case .connecting, .retrievingContext, .generatingResponse, .streaming:
            return true
        default:
            return false
        }
    }
    
    var displayText: String {
        switch self {
        case .idle, .completed:
            return "Ready"
        case .connecting:
            return "Connecting..."
        case .retrievingContext:
            return "Retrieving context..."
        case .generatingResponse:
            return "Thinking..."
        case .streaming:
            return "Responding..."
        case .error(let msg):
            return "Error: \(msg)"
        }
    }
}

// MARK: - Upload Response Models
struct UploadResponse: Codable {
    let status: String
    let message: String
    let filename: String?
    let fileSizeBytes: Int?
    let documentHash: String?
    let chunksStored: Int?
    let chunksSkipped: Int?
    let totalChunksInCollection: Int?
    let originalFileSaved: Bool?
    let processingSettings: ProcessingSettings?
    let chunkingStatistics: ChunkingStatistics?
    let existingChunks: Int? // For duplicate detection
    
    enum CodingKeys: String, CodingKey {
        case status, message, filename
        case fileSizeBytes = "file_size_bytes"
        case documentHash = "document_hash"
        case chunksStored = "chunks_stored"
        case chunksSkipped = "chunks_skipped"
        case totalChunksInCollection = "total_chunks_in_collection"
        case originalFileSaved = "original_file_saved"
        case processingSettings = "processing_settings"
        case chunkingStatistics = "chunking_statistics"
        case existingChunks = "existing_chunks"
    }
}

struct ProcessingSettings: Codable {
    let chunkSize: Int
    let chunkOverlap: Int
    let minChunkLength: Int
    let documentType: String?
    let chunkingMethod: String?
    
    enum CodingKeys: String, CodingKey {
        case chunkSize = "chunk_size"
        case chunkOverlap = "chunk_overlap"
        case minChunkLength = "min_chunk_length"
        case documentType = "document_type"
        case chunkingMethod = "chunking_method"
    }
}

// MARK: - Chunking Statistics
struct ChunkingStatistics: Codable {
    let chunkTypes: [String: Int]
    let totalWords: Int
    let totalSentences: Int
    let avgWordsPerChunk: Double
    let avgSentencesPerChunk: Double
    
    enum CodingKeys: String, CodingKey {
        case chunkTypes = "chunk_types"
        case totalWords = "total_words"
        case totalSentences = "total_sentences"
        case avgWordsPerChunk = "avg_words_per_chunk"
        case avgSentencesPerChunk = "avg_sentences_per_chunk"
    }
}

// MARK: - File List Response Models
struct FileListResponse: Codable {
    let companyId: String
    let documents: [DocumentMetadata]
    let totalDocuments: Int
    let collectionStats: CollectionStats
    
    enum CodingKeys: String, CodingKey {
        case companyId = "company_id"
        case documents
        case totalDocuments = "total_documents"
        case collectionStats = "collection_stats"
    }
}

struct DocumentMetadata: Codable, Identifiable {
    let filename: String
    let documentHash: String
    let fileSizeBytes: Int
    let chunksStored: Int
    let uploadTimestamp: String
    let companyId: String
    
    // Computed properties
    var id: String { documentHash }
    var uploadDate: Date {
        let formatter = ISO8601DateFormatter()
        return formatter.date(from: uploadTimestamp) ?? Date()
    }
    var fileSizeMB: Double {
        return Double(fileSizeBytes) / (1024 * 1024)
    }
    
    enum CodingKeys: String, CodingKey {
        case filename
        case documentHash = "document_hash"
        case fileSizeBytes = "file_size_bytes"
        case chunksStored = "chunks_stored"
        case uploadTimestamp = "upload_timestamp"
        case companyId = "company_id"
    }
}

struct CollectionStats: Codable {
    let namespace: String
    let totalChunks: Int
    let sampleChunks: Int
    let status: String
    let estimatedDocuments: Int?
    let error: String?
    
    enum CodingKeys: String, CodingKey {
        case namespace
        case totalChunks = "total_chunks"
        case sampleChunks = "sample_chunks"
        case status
        case estimatedDocuments = "estimated_documents"
        case error
    }
}

// MARK: - Delete Response Models
struct DeleteResponse: Codable {
    let status: String
    let filename: String
    let chunksDeleted: Int
    let documentHash: String
    let metadataRemoved: Bool
    let warning: String?
    
    enum CodingKeys: String, CodingKey {
        case status, filename, warning
        case chunksDeleted = "chunks_deleted"
        case documentHash = "document_hash"
        case metadataRemoved = "metadata_removed"
    }
}

// MARK: - System Info Models
struct SystemInfoResponse: Codable {
    let databaseInfo: DatabaseInfo
    let dataDirectories: [String: String]
    let settings: SystemSettings
    let status: String
    
    enum CodingKeys: String, CodingKey {
        case databaseInfo = "database_info"
        case dataDirectories = "data_directories"
        case settings, status
    }
}

struct DatabaseInfo: Codable {
    let totalCollections: Int
    let collections: [CollectionInfo]
    let databasePath: String
    let error: String?
    
    enum CodingKeys: String, CodingKey {
        case totalCollections = "total_collections"
        case collections
        case databasePath = "database_path"
        case error
    }
}

struct CollectionInfo: Codable {
    let name: String
    let count: Int
}

struct SystemSettings: Codable {
    let chunkSize: Int
    let chunkOverlap: Int
    let retrievalTopK: Int
    let maxFileSizeMB: Int
    let supportedFileTypes: [String]
    
    enum CodingKeys: String, CodingKey {
        case chunkSize = "chunk_size"
        case chunkOverlap = "chunk_overlap"
        case retrievalTopK = "retrieval_top_k"
        case maxFileSizeMB = "max_file_size_mb"
        case supportedFileTypes = "supported_file_types"
    }
}

// MARK: - Local App Models
enum UploadStatus: String, Codable {
    case uploading
    case uploaded
    case failed
    case duplicate
}

struct UploadedFile: Identifiable, Codable, Equatable {
    let id: UUID
    let filename: String
    let serverPath: String
    let uploadDate: Date
    var status: UploadStatus
    
    // Enhanced properties from server metadata
    var fileSizeBytes: Int?
    var chunksStored: Int?
    var documentHash: String?
    var processingInfo: String?
    
    static func == (lhs: UploadedFile, rhs: UploadedFile) -> Bool {
        return lhs.id == rhs.id
    }
}
