//
//  KeychainServiceTests.swift
//  LiveTranslatorTests
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Unit tests for KeychainService
//

import XCTest
@testable import LiveTranslator

class KeychainServiceTests: XCTestCase {
    var keychainService: KeychainService!
    
    override func setUp() {
        super.setUp()
        keychainService = KeychainService.shared
        // Clean up any existing token
        try? keychainService.deleteToken()
    }
    
    override func tearDown() {
        // Clean up after tests
        try? keychainService.deleteToken()
        super.tearDown()
    }
    
    func testSaveAndRetrieveToken() throws {
        // Given
        let token = "test_jwt_token_12345"
        
        // When
        try keychainService.saveToken(token)
        let retrieved = try keychainService.retrieveToken()
        
        // Then
        XCTAssertEqual(retrieved, token, "Retrieved token should match saved token")
    }
    
    func testDeleteToken() throws {
        // Given
        let token = "test_jwt_token_12345"
        try keychainService.saveToken(token)
        
        // When
        try keychainService.deleteToken()
        
        // Then
        XCTAssertThrowsError(try keychainService.retrieveToken()) { error in
            XCTAssertTrue(error is KeychainError, "Should throw KeychainError")
            if let keychainError = error as? KeychainError,
               case .tokenNotFound = keychainError {
                // Expected error
            } else {
                XCTFail("Should throw tokenNotFound error")
            }
        }
    }
    
    func testHasToken() throws {
        // Given: No token initially
        XCTAssertFalse(keychainService.hasToken(), "Should not have token initially")
        
        // When: Save token
        try keychainService.saveToken("test_token")
        
        // Then: Should have token
        XCTAssertTrue(keychainService.hasToken(), "Should have token after saving")
        
        // When: Delete token
        try keychainService.deleteToken()
        
        // Then: Should not have token
        XCTAssertFalse(keychainService.hasToken(), "Should not have token after deletion")
    }
    
    func testRetrieveNonExistentToken() {
        // When/Then
        XCTAssertThrowsError(try keychainService.retrieveToken()) { error in
            XCTAssertTrue(error is KeychainError)
        }
    }
    
    func testOverwriteExistingToken() throws {
        // Given
        let firstToken = "first_token"
        let secondToken = "second_token"
        
        // When
        try keychainService.saveToken(firstToken)
        try keychainService.saveToken(secondToken)
        let retrieved = try keychainService.retrieveToken()
        
        // Then
        XCTAssertEqual(retrieved, secondToken, "Second token should overwrite first")
    }
}
