//
//  AuthServiceTests.swift
//  LiveTranslatorTests
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Unit tests for AuthService
//

import XCTest
@testable import LiveTranslator

class AuthServiceTests: XCTestCase {
    var authService: AuthService!
    var mockKeychainService: MockKeychainService!
    
    override func setUp() {
        super.setUp()
        mockKeychainService = MockKeychainService()
        authService = AuthService(keychainService: mockKeychainService)
    }
    
    func testIsAuthenticatedWhenTokenExists() {
        // Given
        mockKeychainService.mockToken = "fake_jwt_token"
        
        // When
        let isAuthenticated = authService.isAuthenticated()
        
        // Then
        XCTAssertTrue(isAuthenticated)
    }
    
    func testIsAuthenticatedWhenNoToken() {
        // Given
        mockKeychainService.mockToken = nil
        
        // When
        let isAuthenticated = authService.isAuthenticated()
        
        // Then
        XCTAssertFalse(isAuthenticated)
    }
    
    func testLoginWithGoogleExtractsTokenFromURL() async throws {
        // Given
        let jwt = createMockJWT(userId: 1, email: "test@example.com")
        let callbackURL = URL(string: "livetranslator://auth/google/callback?token=\(jwt)")!
        
        // When
        let user = try await authService.loginWithGoogle(callbackURL: callbackURL)
        
        // Then
        XCTAssertEqual(user.id, 1)
        XCTAssertEqual(user.email, "test@example.com")
        XCTAssertEqual(mockKeychainService.savedToken, jwt)
    }
    
    func testLoginWithGoogleFailsWithInvalidURL() async {
        // Given
        let callbackURL = URL(string: "livetranslator://auth/google/callback")!  // No token param
        
        // When/Then
        do {
            _ = try await authService.loginWithGoogle(callbackURL: callbackURL)
            XCTFail("Should throw error")
        } catch {
            XCTAssertTrue(error is AuthError)
        }
    }
    
    // MARK: - Helper Methods
    
    private func createMockJWT(userId: Int, email: String) -> String {
        // Create a simplified JWT for testing
        // Format: header.payload.signature (we only care about payload for testing)
        let header = ["alg": "HS256", "typ": "JWT"]
        let payload: [String: Any] = [
            "sub": "\(userId)",
            "email": email,
            "preferred_lang": "en",
            "is_admin": false,
            "exp": Date().addingTimeInterval(3600).timeIntervalSince1970
        ]
        
        let headerData = try! JSONSerialization.data(withJSONObject: header)
        let payloadData = try! JSONSerialization.data(withJSONObject: payload)
        
        let headerBase64 = headerData.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
        
        let payloadBase64 = payloadData.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
        
        return "\(headerBase64).\(payloadBase64).fake_signature"
    }
}

// MARK: - Mock Classes

class MockKeychainService: KeychainService {
    var mockToken: String?
    var savedToken: String?
    
    override func saveToken(_ token: String) throws {
        savedToken = token
        mockToken = token
    }
    
    override func retrieveToken() throws -> String {
        guard let token = mockToken else {
            throw KeychainError.tokenNotFound
        }
        return token
    }
    
    override func deleteToken() throws {
        mockToken = nil
        savedToken = nil
    }
    
    override func hasToken() -> Bool {
        return mockToken != nil
    }
}
