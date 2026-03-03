//
//  SignupView.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Email/password signup screen
//

import SwiftUI

struct SignupView: View {
    @EnvironmentObject var authViewModel: AuthViewModel
    @State private var showPassword = false
    @Environment(\.presentationMode) var presentationMode
    
    var body: some View {
        Form {
            Section(header: Text("Account Information")) {
                TextField("Email", text: $authViewModel.email)
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
                    .textContentType(.emailAddress)
                
                HStack {
                    if showPassword {
                        TextField("Password", text: $authViewModel.password)
                            .textContentType(.newPassword)
                    } else {
                        SecureField("Password", text: $authViewModel.password)
                            .textContentType(.newPassword)
                    }
                    
                    Button(action: { showPassword.toggle() }) {
                        Image(systemName: showPassword ? "eye.slash" : "eye")
                            .foregroundColor(.gray)
                    }
                    .buttonStyle(.plain)
                }
                
                TextField("Display Name (Optional)", text: $authViewModel.displayName)
                    .textContentType(.name)
            } footer: {
                Text("Password must be at least 8 characters.")
                    .font(.caption)
            }
            
            Section {
                Button(action: {
                    Task {
                        await authViewModel.signup()
                        if authViewModel.isAuthenticated {
                            presentationMode.wrappedValue.dismiss()
                        }
                    }
                }) {
                    HStack {
                        Spacer()
                        if authViewModel.isLoading {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle())
                        } else {
                            Text("Sign Up")
                                .fontWeight(.semibold)
                        }
                        Spacer()
                    }
                }
                .disabled(authViewModel.isLoading)
            }
            
            if let error = authViewModel.errorMessage {
                Section {
                    Text(error)
                        .foregroundColor(.red)
                        .font(.callout)
                }
            }
            
            Section {
                Button(action: {
                    presentationMode.wrappedValue.dismiss()
                }) {
                    HStack {
                        Spacer()
                        Text("Already have an account? Login")
                            .font(.callout)
                        Spacer()
                    }
                }
            }
        }
        .navigationTitle("Sign Up")
    }
}

struct SignupView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            SignupView()
                .environmentObject(AuthViewModel())
        }
    }
}
