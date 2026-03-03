//
//  APIClientTests.swift
//  LiveTranslatorTests
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Unit tests for APIClient
//

import XCTest
@testable import LiveTranslator

class APIClientTests: XCTestCase {
    var apiClient: APIClient!
    var mockSession: URLSession!
    var mockKeychainService: MockKeychainService!
    
    override func setUp() async throws {
        try await super.setUp()
        
        // Configure mock URLSession
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        mockSession = URLSession(configuration: config)
        
        mockKeychainService = MockKeychainService()
        apiClient = await APIClient(session: mockSession, keychainService: mockKeychainService)
    }
    
    func testRequestSuccessWithJSONResponse() async throws {
        // Given
        let mockResponse = AuthResponse(accessToken: "fake_jwt_token")
        MockURLProtocol.mockData = try JSONEncoder().encode(mockResponse)
        MockURLProtocol.mockStatusCode = 200
        
        // When
        let response: AuthResponse = try await apiClient.request("/auth/signup", method: .POST)
        
        // Then
        XCTAssertEqual(response.accessToken, "fake_jwt_token")
    }
    
    func testRequest401UnauthorizedError() async {
        // Given
        MockURLProtocol.mockData = Data()
        MockURLProtocol.mockStatusCode = 401
        
        // When/Then
        do {
            let _: AuthResponse = try await apiClient.request("/auth/login", method: .POST)
            XCTFail("Should throw error")
        } catch APIError.httpError(let code, _) {
            XCTAssertEqual(code, 401)
        } catch {
            XCTFail("Wrong error type: \(error)")
        }
    }
    
    func testRequest400BadRequestWithMessage() async {
        // Given
        let errorDict = ["detail": "email_exists"]
        MockURLProtocol.mockData = try! JSONEncoder().encode(errorDict)
        MockURLProtocol.mockStatusCode = 400
        
        // When/Then
        do {
            let _: AuthResponse = try await apiClient.request("/auth/signup", method: .POST)
            XCTFail("Should throw error")
        } catch APIError.httpError(let code, let message) {
            XCTAssertEqual(code, 400)
            XCTAssertEqual(message, "email_exists")
        } catch {
            XCTFail("Wrong error type: \(error)")
        }
    }
    
    func testRequestInjectsJWTTokenWhenAvailable() async throws {
        // Given
        mockKeychainService.mockToken = "Bearer test_token"
        MockURLProtocol.mockData = try JSONEncoder().encode(["status": "ok"])
        MockURLProtocol.mockStatusCode = 200
        
        // When
        struct Response: Codable { let status: String }
        let _: Response = try await apiClient.request("/api/profile", method: .GET, requiresAuth: true)
        
        // Then
        XCTAssertNotNil(MockURLProtocol.lastRequest?.value(forHTTPHeaderField: "Authorization"))
    }
}

// MARK: - Mock URLProtocol

class MockURLProtocol: URLProtocol {
    static var mockData: Data?
    static var mockStatusCode: Int = 200
    static var mockError: Error?
    static var lastRequest: URLRequest?
    
    override class func canInit(with request: URLRequest) -> Bool {
        lastRequest = request
        return true
    }
    
    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        return request
    }
    
    override func startLoading() {
        if let error = Self.mockError {
            client?.urlProtocol(self, didFailWithError: error)
        } else {
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: Self.mockStatusCode,
                httpVersion: nil,
                headerFields: nil
            )!
            
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            
            if let data = Self.mockData {
                client?.urlProtocol(self, didLoad: data)
            }
        }
        
        client?.urlProtocolDidFinishLoading(self)
    }
    
    override func stopLoading() {
        // No-op
    }
}
