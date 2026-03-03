//
//  AuthService.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Authentication business logic and token management
//

import Foundation

enum AuthError: Error, LocalizedError {
    case invalidToken
    case emailExists
    case invalidCredentials
    case googleAuthFailed(String)
    
    var errorDescription: String? {
        switch self {
        case .invalidToken:
            return "Invalid authentication token"
        case .emailExists:
            return "This email is already registered. Please log in."
        case .invalidCredentials:
            return "Invalid email or password."
        case .googleAuthFailed(let message):
            return "Google sign-in failed: \(message)"
        }
    }
}

class AuthService {
    private let apiClient: APIClient
    private let keychainService: KeychainService
    
    init(apiClient: APIClient = .shared, keychainService: KeychainService = .shared) {
        self.apiClient = apiClient
        self.keychainService = keychainService
    }
    
    /// Sign up with email and password
    func signup(email: String, password: String, displayName: String?) async throws -> User {
        let request = SignupRequest(
            email: email,
            password: password,
            displayName: displayName?.isEmpty == false ? displayName : nil
        )
        
        do {
            let response: AuthResponse = try await apiClient.request(
                "/auth/signup",
                method: .POST,
                body: request
            )
            
            // Save token to Keychain
            try keychainService.saveToken(response.accessToken)
            
            // Decode JWT to extract user info
            return try decodeJWT(response.accessToken)
            
        } catch APIError.httpError(let code, let message) where code == 400 {
            if message?.contains("email_exists") == true {
                throw AuthError.emailExists
            }
            throw APIError.httpError(statusCode: code, message: message)
        }
    }
    
    /// Log in with email and password (OAuth2PasswordRequestForm)
    func login(email: String, password: String) async throws -> User {
        let formData = [
            "username": email,  // OAuth2PasswordRequestForm uses "username" field
            "password": password
        ]
        
        do {
            let response: AuthResponse = try await apiClient.requestFormEncoded(
                "/auth/login",
                method: .POST,
                formData: formData
            )
            
            // Save token to Keychain
            try keychainService.saveToken(response.accessToken)
            
            // Decode JWT to extract user info
            return try decodeJWT(response.accessToken)
            
        } catch APIError.httpError(let code, _) where code == 401 {
            throw AuthError.invalidCredentials
        }
    }
    
    /// Log in with Google OAuth (extract JWT from callback URL)
    func loginWithGoogle(callbackURL: URL) async throws -> User {
        // Extract token from callback URL
        // Expected format: livetranslator://auth/google/callback?token={jwt}
        guard let components = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false),
              let token = components.queryItems?.first(where: { $0.name == "token" })?.value else {
            throw AuthError.googleAuthFailed("Failed to extract token from callback URL")
        }
        
        // Save token to Keychain
        try keychainService.saveToken(token)
        
        // Decode JWT to extract user info
        return try decodeJWT(token)
    }
    
    /// Log out (delete token from Keychain)
    func logout() async throws {
        // Optionally call backend logout endpoint
        // try await apiClient.request<[String: String]>("/auth/logout", method: .POST)
        
        // Delete token from Keychain
        try keychainService.deleteToken()
    }
    
    /// Get current authenticated user from JWT token
    func getCurrentUser() async throws -> User {
        guard let token = try? keychainService.retrieveToken() else {
            throw AuthError.invalidToken
        }
        
        return try decodeJWT(token)
    }
    
    /// Check if user is authenticated (has valid token in Keychain)
    func isAuthenticated() -> Bool {
        return keychainService.hasToken()
    }
    
    // MARK: - Private Helpers
    
    /// Decode JWT token to extract user info
    /// Note: This is a simplified JWT decoder. For production, consider using a library like JWTDecode.
    private func decodeJWT(_ token: String) throws -> User {
        let segments = token.components(separatedBy: ".")
        guard segments.count == 3 else {
            throw AuthError.invalidToken
        }
        
        // Decode payload (second segment)
        let payloadSegment = segments[1]
        
        // Add padding if needed (base64 requires padding)
        var base64 = payloadSegment
            .replacingOccurrences(of: "-", with: "+")
            .replacingOccurrences(of: "_", with: "/")
        
        let paddingLength = 4 - (base64.count % 4)
        if paddingLength < 4 {
            base64 += String(repeating: "=", count: paddingLength)
        }
        
        // Decode base64
        guard let payloadData = Data(base64Encoded: base64) else {
            throw AuthError.invalidToken
        }
        
        // Parse JSON
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .secondsSince1970
        
        struct JWTPayload: Codable {
            let sub: String          // user_id
            let email: String
            let preferredLang: String?
            let isAdmin: Bool?
            let exp: TimeInterval
            
            enum CodingKeys: String, CodingKey {
                case sub, email, exp
                case preferredLang = "preferred_lang"
                case isAdmin = "is_admin"
            }
        }
        
        let payload = try decoder.decode(JWTPayload.self, from: payloadData)
        
        // Check expiration
        let expirationDate = Date(timeIntervalSince1970: payload.exp)
        if expirationDate < Date() {
            throw AuthError.invalidToken
        }
        
        // Convert to User model
        guard let userId = Int(payload.sub) else {
            throw AuthError.invalidToken
        }
        
        return User(
            id: userId,
            email: payload.email,
            displayName: "",  // Not in JWT, will be fetched from API if needed
            preferredLang: payload.preferredLang ?? "en",
            isAdmin: payload.isAdmin ?? false,
            createdAt: Date()  // Not in JWT, placeholder
        )
    }
}
