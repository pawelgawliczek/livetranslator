//
//  GoogleAuthView.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Google OAuth authentication flow using ASWebAuthenticationSession
//

import SwiftUI
import AuthenticationServices

struct GoogleAuthView: View {
    @EnvironmentObject var authViewModel: AuthViewModel
    @Environment(\.presentationMode) var presentationMode
    @State private var authSession: ASWebAuthenticationSession?
    
    var body: some View {
        VStack(spacing: 20) {
            ProgressView()
                .scaleEffect(1.5)
            
            Text("Redirecting to Google...")
                .font(.headline)
            
            Button("Cancel") {
                authSession?.cancel()
                presentationMode.wrappedValue.dismiss()
            }
            .padding(.top, 20)
        }
        .padding()
        .onAppear {
            startGoogleOAuth()
        }
    }
    
    private func startGoogleOAuth() {
        guard let authURL = URL(string: "https://livetranslator.pawelgawliczek.cloud/auth/google/login") else {
            authViewModel.errorMessage = "Invalid authentication URL"
            presentationMode.wrappedValue.dismiss()
            return
        }
        
        let callbackScheme = "livetranslator"
        
        authSession = ASWebAuthenticationSession(
            url: authURL,
            callbackURLScheme: callbackScheme
        ) { callbackURL, error in
            if let error = error {
                // User cancelled or error occurred
                if (error as? ASWebAuthenticationSessionError)?.code == .canceledLogin {
                    // User cancelled, dismiss silently
                } else {
                    authViewModel.errorMessage = "Google authentication failed: \(error.localizedDescription)"
                }
                presentationMode.wrappedValue.dismiss()
                return
            }
            
            if let url = callbackURL {
                Task {
                    await authViewModel.loginWithGoogle(callbackURL: url)
                    presentationMode.wrappedValue.dismiss()
                }
            }
        }
        
        authSession?.prefersEphemeralWebBrowserSession = false
        authSession?.presentationContextProvider = PresentationContextProvider()
        authSession?.start()
    }
}

// Helper class to provide presentation context for ASWebAuthenticationSession
class PresentationContextProvider: NSObject, ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        return UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }
            .first { $0.isKeyWindow } ?? ASPresentationAnchor()
    }
}

struct GoogleAuthView_Previews: PreviewProvider {
    static var previews: some View {
        GoogleAuthView()
            .environmentObject(AuthViewModel())
    }
}
