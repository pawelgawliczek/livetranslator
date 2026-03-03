//
//  AuthViewModel.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Authentication state management for Views
//

import SwiftUI

@MainActor
class AuthViewModel: ObservableObject {
    // Input fields
    @Published var email: String = ""
    @Published var password: String = ""
    @Published var displayName: String = ""
    
    // UI state
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var isAuthenticated: Bool = false
    
    private let authService: AuthService
    
    init(authService: AuthService = AuthService()) {
        self.authService = authService
        self.isAuthenticated = authService.isAuthenticated()
    }
    
    /// Sign up with email and password
    func signup() async {
        guard validateSignup() else { return }
        
        isLoading = true
        errorMessage = nil
        
        do {
            _ = try await authService.signup(
                email: email.trimmingCharacters(in: .whitespaces),
                password: password,
                displayName: displayName.isEmpty ? nil : displayName.trimmingCharacters(in: .whitespaces)
            )
            isAuthenticated = true
            clearFields()
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
    
    /// Log in with email and password
    func login() async {
        guard validateLogin() else { return }
        
        isLoading = true
        errorMessage = nil
        
        do {
            _ = try await authService.login(
                email: email.trimmingCharacters(in: .whitespaces),
                password: password
            )
            isAuthenticated = true
            clearFields()
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
    
    /// Log in with Google OAuth callback
    func loginWithGoogle(callbackURL: URL) async {
        isLoading = true
        errorMessage = nil
        
        do {
            _ = try await authService.loginWithGoogle(callbackURL: callbackURL)
            isAuthenticated = true
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
    
    /// Log out
    func logout() async {
        do {
            try await authService.logout()
            isAuthenticated = false
            clearFields()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
    
    // MARK: - Validation
    
    private func validateSignup() -> Bool {
        errorMessage = nil
        
        // Email validation
        let emailRegex = "[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}"
        let emailPredicate = NSPredicate(format:"SELF MATCHES %@", emailRegex)
        guard emailPredicate.evaluate(with: email.trimmingCharacters(in: .whitespaces)) else {
            errorMessage = "Please enter a valid email address."
            return false
        }
        
        // Password validation
        guard password.count >= 8 else {
            errorMessage = "Password must be at least 8 characters."
            return false
        }
        
        // Display name validation (optional, but if provided must be <= 120 chars)
        if !displayName.isEmpty && displayName.count > 120 {
            errorMessage = "Display name must be 120 characters or less."
            return false
        }
        
        return true
    }
    
    private func validateLogin() -> Bool {
        errorMessage = nil
        
        // Email validation
        let emailRegex = "[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}"
        let emailPredicate = NSPredicate(format:"SELF MATCHES %@", emailRegex)
        guard emailPredicate.evaluate(with: email.trimmingCharacters(in: .whitespaces)) else {
            errorMessage = "Please enter a valid email address."
            return false
        }
        
        // Password validation
        guard !password.isEmpty else {
            errorMessage = "Please enter your password."
            return false
        }
        
        return true
    }
    
    private func clearFields() {
        email = ""
        password = ""
        displayName = ""
    }
}
