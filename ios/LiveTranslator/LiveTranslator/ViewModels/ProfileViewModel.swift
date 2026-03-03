//
//  ProfileViewModel.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Profile state management for Views
//

import SwiftUI

@MainActor
class ProfileViewModel: ObservableObject {
    @Published var user: User?
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    
    private let authService: AuthService
    
    init(authService: AuthService = AuthService()) {
        self.authService = authService
    }
    
    /// Load current user from JWT token
    func loadUser() async {
        isLoading = true
        errorMessage = nil
        
        do {
            user = try await authService.getCurrentUser()
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
    
    /// Log out
    func logout() async {
        do {
            try await authService.logout()
            user = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
