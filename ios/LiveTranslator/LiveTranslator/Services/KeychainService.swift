//
//  KeychainService.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Secure JWT token storage in iOS Keychain
//

import Foundation
import Security

enum KeychainError: Error, LocalizedError {
    case unableToSave(OSStatus)
    case unableToRetrieve(OSStatus)
    case unableToDelete(OSStatus)
    case tokenNotFound
    case unexpectedData
    
    var errorDescription: String? {
        switch self {
        case .unableToSave(let status):
            return "Failed to save token to Keychain (status: \(status))"
        case .unableToRetrieve(let status):
            return "Failed to retrieve token from Keychain (status: \(status))"
        case .unableToDelete(let status):
            return "Failed to delete token from Keychain (status: \(status))"
        case .tokenNotFound:
            return "Token not found in Keychain"
        case .unexpectedData:
            return "Unexpected data format in Keychain"
        }
    }
}

class KeychainService {
    static let shared = KeychainService()
    
    private let service = "com.livetranslator.ios"
    private let account = "jwt_token"
    
    private init() {}
    
    /// Save JWT token to Keychain
    func saveToken(_ token: String) throws {
        guard let data = token.data(using: .utf8) else {
            throw KeychainError.unexpectedData
        }
        
        // Delete existing token first (if any)
        try? deleteToken()
        
        // Create query dictionary
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]
        
        // Add to Keychain
        let status = SecItemAdd(query as CFDictionary, nil)
        
        guard status == errSecSuccess else {
            throw KeychainError.unableToSave(status)
        }
    }
    
    /// Retrieve JWT token from Keychain
    func retrieveToken() throws -> String {
        // Create query dictionary
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        // Search Keychain
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        
        guard status == errSecSuccess else {
            if status == errSecItemNotFound {
                throw KeychainError.tokenNotFound
            }
            throw KeychainError.unableToRetrieve(status)
        }
        
        // Extract data
        guard let data = result as? Data,
              let token = String(data: data, encoding: .utf8) else {
            throw KeychainError.unexpectedData
        }
        
        return token
    }
    
    /// Delete JWT token from Keychain
    func deleteToken() throws {
        // Create query dictionary
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        
        // Delete from Keychain
        let status = SecItemDelete(query as CFDictionary)
        
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.unableToDelete(status)
        }
    }
    
    /// Check if JWT token exists in Keychain
    func hasToken() -> Bool {
        return (try? retrieveToken()) != nil
    }
}
