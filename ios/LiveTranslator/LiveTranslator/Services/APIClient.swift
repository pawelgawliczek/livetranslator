//
//  APIClient.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  HTTP client for backend API communication
//

import Foundation

enum HTTPMethod: String {
    case GET, POST, PUT, DELETE, PATCH
}

enum APIError: Error, LocalizedError {
    case invalidURL
    case networkError(Error)
    case httpError(statusCode: Int, message: String?)
    case decodingError(Error)
    case unauthorized
    case noData
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .httpError(let code, let msg):
            if code == 401 {
                return msg ?? "Unauthorized. Please log in again."
            } else if code == 400 {
                return msg ?? "Bad request"
            }
            return "HTTP \(code): \(msg ?? "Unknown error")"
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .unauthorized:
            return "Unauthorized. Please log in again."
        case .noData:
            return "No data received from server"
        }
    }
}

actor APIClient {
    static let shared = APIClient()
    
    private let baseURL = "https://livetranslator.pawelgawliczek.cloud"
    private let session: URLSession
    private let keychainService: KeychainService
    
    init(session: URLSession = .shared, keychainService: KeychainService = .shared) {
        self.session = session
        self.keychainService = keychainService
    }
    
    /// Generic request method with automatic JWT token injection
    func request<T: Decodable>(
        _ endpoint: String,
        method: HTTPMethod,
        body: Encodable? = nil,
        requiresAuth: Bool = false
    ) async throws -> T {
        // 1. Build URL
        guard let url = URL(string: baseURL + endpoint) else {
            throw APIError.invalidURL
        }
        
        // 2. Create request
        var request = URLRequest(url: url)
        request.httpMethod = method.rawValue
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // 3. Inject JWT token if available
        if requiresAuth {
            if let token = try? keychainService.retrieveToken() {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            } else {
                throw APIError.unauthorized
            }
        } else {
            // Try to inject token if available (optional auth)
            if let token = try? keychainService.retrieveToken() {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }
        }
        
        // 4. Encode body if present
        if let body = body {
            request.httpBody = try JSONEncoder().encode(body)
        }
        
        // 5. Execute request
        let (data, response) = try await session.data(for: request)
        
        // 6. Handle HTTP errors
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError(NSError(domain: "Invalid response", code: -1))
        }
        
        guard (200...299).contains(httpResponse.statusCode) else {
            // Try to extract error message from response body
            let errorMessage = try? JSONDecoder().decode([String: String].self, from: data)
            throw APIError.httpError(
                statusCode: httpResponse.statusCode,
                message: errorMessage?["detail"] ?? errorMessage?["message"]
            )
        }
        
        // 7. Decode response
        do {
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }
    
    /// Request method for OAuth2PasswordRequestForm (login endpoint)
    func requestFormEncoded<T: Decodable>(
        _ endpoint: String,
        method: HTTPMethod,
        formData: [String: String]
    ) async throws -> T {
        // 1. Build URL
        guard let url = URL(string: baseURL + endpoint) else {
            throw APIError.invalidURL
        }
        
        // 2. Create request
        var request = URLRequest(url: url)
        request.httpMethod = method.rawValue
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        
        // 3. Encode form data
        var components = URLComponents()
        components.queryItems = formData.map { URLQueryItem(name: $0.key, value: $0.value) }
        request.httpBody = components.query?.data(using: .utf8)
        
        // 4. Execute request
        let (data, response) = try await session.data(for: request)
        
        // 5. Handle HTTP errors
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError(NSError(domain: "Invalid response", code: -1))
        }
        
        guard (200...299).contains(httpResponse.statusCode) else {
            let errorMessage = try? JSONDecoder().decode([String: String].self, from: data)
            throw APIError.httpError(
                statusCode: httpResponse.statusCode,
                message: errorMessage?["detail"] ?? errorMessage?["message"]
            )
        }
        
        // 6. Decode response
        do {
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }
}
