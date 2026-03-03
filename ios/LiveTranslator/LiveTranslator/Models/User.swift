//
//  User.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  User model matching backend API schema
//

import Foundation

struct User: Codable, Identifiable, Equatable {
    let id: Int
    let email: String
    let displayName: String
    let preferredLang: String
    let isAdmin: Bool
    let createdAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id, email, isAdmin
        case displayName = "display_name"
        case preferredLang = "preferred_lang"
        case createdAt = "created_at"
    }
}
