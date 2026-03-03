//
//  ProfileView.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  User profile display and management
//

import SwiftUI

struct ProfileView: View {
    @StateObject private var viewModel = ProfileViewModel()
    @EnvironmentObject var authViewModel: AuthViewModel
    @State private var showLogoutConfirmation = false
    
    var body: some View {
        NavigationView {
            Group {
                if viewModel.isLoading {
                    ProgressView()
                } else if let user = viewModel.user {
                    Form {
                        Section(header: Text("Account")) {
                            LabeledContent("Email", value: user.email)
                            LabeledContent("Display Name", value: user.displayName.isEmpty ? "Not set" : user.displayName)
                            LabeledContent("Preferred Language", value: user.preferredLang)
                            LabeledContent("Account Type", value: user.isAdmin ? "Admin" : "User")
                        }
                        
                        Section(header: Text("Subscription")) {
                            LabeledContent("Plan", value: "Free")
                            Text("Upgrade to Plus or Pro for unlimited usage")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        
                        Section {
                            NavigationLink(destination: ProfileEditView(user: user)) {
                                Label("Edit Profile", systemImage: "pencil")
                            }
                        }
                        
                        Section {
                            Button(role: .destructive, action: {
                                showLogoutConfirmation = true
                            }) {
                                HStack {
                                    Spacer()
                                    Label("Logout", systemImage: "rectangle.portrait.and.arrow.right")
                                    Spacer()
                                }
                            }
                        }
                    }
                    .refreshable {
                        await viewModel.loadUser()
                    }
                } else {
                    VStack(spacing: 20) {
                        Image(systemName: "person.crop.circle.badge.exclamationmark")
                            .font(.system(size: 64))
                            .foregroundColor(.gray)
                        
                        Text("Unable to load profile")
                            .font(.headline)
                        
                        if let error = viewModel.errorMessage {
                            Text(error)
                                .font(.callout)
                                .foregroundColor(.red)
                                .multilineTextAlignment(.center)
                                .padding()
                        }
                        
                        Button("Retry") {
                            Task {
                                await viewModel.loadUser()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .padding()
                }
            }
            .navigationTitle("Profile")
            .task {
                await viewModel.loadUser()
            }
            .alert("Logout", isPresented: $showLogoutConfirmation) {
                Button("Cancel", role: .cancel) {}
                Button("Logout", role: .destructive) {
                    Task {
                        await authViewModel.logout()
                    }
                }
            } message: {
                Text("Are you sure you want to log out?")
            }
        }
    }
}

struct ProfileView_Previews: PreviewProvider {
    static var previews: some View {
        ProfileView()
            .environmentObject(AuthViewModel())
    }
}
