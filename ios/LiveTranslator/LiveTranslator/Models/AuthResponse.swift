//
//  AuthResponse.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Authentication API response model
//

import Foundation

struct AuthResponse: Codable {
    let accessToken: String
    
    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
    }
}

struct SignupRequest: Codable {
    let email: String
    let password: String
    let displayName: String?
    
    enum CodingKeys: String, CodingKey {
        case email, password
        case displayName = "display_name"
    }
}
