//
//  APIService.swift
//  AIChatApp
//
//  Created by İlhan Akbudak on 25.07.2025.
//

import Foundation
import SwiftUI

class APIService: ObservableObject {
    static let shared = APIService()
    @AppStorage("apiBaseURL") private var baseURLString: String = "http://127.0.0.1:8000"
    
    private var baseURL: URL? {
        URL(string: baseURLString)
    }
    
    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        return decoder
    }()
    
    // MARK: - Chat API
    func sendMessage(_ message: String, companyID: String, completion: @escaping (Result<String, Error>) -> Void) {
        guard let baseURL = baseURL else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        let url = baseURL.appendingPathComponent("chat/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = [
            "message": message,
            "company_id": companyID
        ]

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        } catch {
            completion(.failure(error))
            return
        }

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }

            do {
                if let response = try JSONSerialization.jsonObject(with: data) as? [String: String],
                   let reply = response["response"] {
                    completion(.success(reply))
                } else {
                    completion(.failure(APIError.invalidResponse))
                }
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
    
    // MARK: - Enhanced Upload API
    func uploadFile(_ fileURL: URL, companyID: String, completion: @escaping (Result<UploadResponse, Error>) -> Void) {
        guard let baseURL = baseURL else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        let url = baseURL.appendingPathComponent("upload/")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        let filename = fileURL.lastPathComponent
        print("Uploading file: \(filename) at path: \(fileURL.path)")

        // Read file data with error handling
        let fileData: Data
        do {
            fileData = try Data(contentsOf: fileURL)
        } catch {
            completion(.failure(APIError.fileReadFailed(error.localizedDescription)))
            return
        }

        // Add file to multipart body
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: application/octet-stream\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n".data(using: .utf8)!)

        // Add company_id
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"company_id\"\r\n\r\n".data(using: .utf8)!)
        body.append(companyID.data(using: .utf8)!)
        body.append("\r\n".data(using: .utf8)!)

        // End boundary
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        URLSession.shared.uploadTask(with: request, from: body) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }

            do {
                let uploadResponse = try self.decoder.decode(UploadResponse.self, from: data)
                completion(.success(uploadResponse))
            } catch {
                // Fallback to old format for error handling
                if let errorResponse = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let errorMsg = errorResponse["error"] as? String {
                    completion(.failure(APIError.serverError(errorMsg)))
                } else {
                    completion(.failure(APIError.decodingFailed(error.localizedDescription)))
                }
            }
        }.resume()
    }
    
    // MARK: - File Management API
    func fetchCompanyFiles(companyID: String, completion: @escaping (Result<FileListResponse, Error>) -> Void) {
        guard let baseURL = baseURL else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        var components = URLComponents(url: baseURL.appendingPathComponent("upload/files"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "company_id", value: companyID)]
        
        guard let url = components?.url else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        URLSession.shared.dataTask(with: url) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            
            do {
                let fileListResponse = try self.decoder.decode(FileListResponse.self, from: data)
                completion(.success(fileListResponse))
            } catch {
                completion(.failure(APIError.decodingFailed(error.localizedDescription)))
            }
        }.resume()
    }
    
    // MARK: - Enhanced Delete API
    func deleteFile(filename: String, companyID: String, completion: @escaping (Result<DeleteResponse, Error>) -> Void) {
        guard let baseURL = baseURL else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        var components = URLComponents(url: baseURL.appendingPathComponent("upload/\(filename)"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "company_id", value: companyID)]
        
        guard let url = components?.url else {
            completion(.failure(APIError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            
            do {
                let deleteResponse = try self.decoder.decode(DeleteResponse.self, from: data)
                completion(.success(deleteResponse))
            } catch {
                completion(.failure(APIError.decodingFailed(error.localizedDescription)))
            }
        }.resume()
    }
    
    // MARK: - System Info API
    func fetchSystemInfo(completion: @escaping (Result<SystemInfoResponse, Error>) -> Void) {
        guard let baseURL = baseURL else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        let url = baseURL.appendingPathComponent("upload/system/info")
        
        URLSession.shared.dataTask(with: url) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            
            do {
                let systemInfo = try self.decoder.decode(SystemInfoResponse.self, from: data)
                completion(.success(systemInfo))
            } catch {
                completion(.failure(APIError.decodingFailed(error.localizedDescription)))
            }
        }.resume()
    }
    
    // MARK: - Connection Testing
    func testConnection(completion: @escaping (Result<Bool, Error>) -> Void) {
        fetchSystemInfo { result in
            switch result {
            case .success:
                completion(.success(true))
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
}

// MARK: - API Error Types
enum APIError: LocalizedError {
    case invalidURL
    case noData
    case invalidResponse
    case serverError(String)
    case fileReadFailed(String)
    case decodingFailed(String)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid API URL"
        case .noData:
            return "No data received from server"
        case .invalidResponse:
            return "Invalid response format"
        case .serverError(let message):
            return "Server error: \(message)"
        case .fileReadFailed(let message):
            return "Failed to read file: \(message)"
        case .decodingFailed(let message):
            return "Failed to decode response: \(message)"
        }
    }
}

