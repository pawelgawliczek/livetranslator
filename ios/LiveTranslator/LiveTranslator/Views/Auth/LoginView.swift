//
//  LoginView.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Email/password login screen
//

import SwiftUI

struct LoginView: View {
    @EnvironmentObject var authViewModel: AuthViewModel
    @State private var showPassword = false
    @State private var showGoogleAuth = false
    
    var body: some View {
        NavigationView {
            ZStack {
                Form {
                    Section {
                        TextField("Email", text: $authViewModel.email)
                            .keyboardType(.emailAddress)
                            .autocapitalization(.none)
                            .textContentType(.emailAddress)
                        
                        HStack {
                            if showPassword {
                                TextField("Password", text: $authViewModel.password)
                                    .textContentType(.password)
                            } else {
                                SecureField("Password", text: $authViewModel.password)
                                    .textContentType(.password)
                            }
                            
                            Button(action: { showPassword.toggle() }) {
                                Image(systemName: showPassword ? "eye.slash" : "eye")
                                    .foregroundColor(.gray)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    
                    Section {
                        Button(action: {
                            Task {
                                await authViewModel.login()
                            }
                        }) {
                            HStack {
                                Spacer()
                                if authViewModel.isLoading {
                                    ProgressView()
                                        .progressViewStyle(CircularProgressViewStyle())
                                } else {
                                    Text("Login")
                                        .fontWeight(.semibold)
                                }
                                Spacer()
                            }
                        }
                        .disabled(authViewModel.isLoading)
                        
                        Button(action: {
                            showGoogleAuth = true
                        }) {
                            HStack {
                                Spacer()
                                Image(systemName: "globe")
                                Text("Continue with Google")
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
                        NavigationLink(destination: SignupView()) {
                            HStack {
                                Spacer()
                                Text("Don't have an account? Sign Up")
                                    .font(.callout)
                                Spacer()
                            }
                        }
                    }
                }
                .navigationTitle("Login")
            }
            .sheet(isPresented: $showGoogleAuth) {
                GoogleAuthView()
            }
        }
    }
}

struct LoginView_Previews: PreviewProvider {
    static var previews: some View {
        LoginView()
            .environmentObject(AuthViewModel())
    }
}
