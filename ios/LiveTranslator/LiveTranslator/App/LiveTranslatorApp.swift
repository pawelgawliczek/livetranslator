//
//  LiveTranslatorApp.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Main app entry point
//

import SwiftUI

@main
struct LiveTranslatorApp: App {
    @StateObject private var authViewModel = AuthViewModel()
    @StateObject private var networkMonitor = NetworkMonitor.shared
    
    var body: some Scene {
        WindowGroup {
            Group {
                if authViewModel.isAuthenticated {
                    ContentView()
                        .environmentObject(authViewModel)
                        .environmentObject(networkMonitor)
                } else {
                    LoginView()
                        .environmentObject(authViewModel)
                        .environmentObject(networkMonitor)
                }
            }
            .overlay(alignment: .top) {
                if !networkMonitor.isConnected {
                    HStack {
                        Image(systemName: "wifi.slash")
                        Text("No Internet Connection")
                            .font(.callout)
                    }
                    .padding()
                    .background(Color.orange.opacity(0.9))
                    .foregroundColor(.white)
                    .cornerRadius(8)
                    .padding(.top, 50)
                    .transition(.move(edge: .top))
                }
            }
        }
    }
}
