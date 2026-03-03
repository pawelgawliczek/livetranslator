//
//  ContentView.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Main TabView navigation
//

import SwiftUI

struct ContentView: View {
    @EnvironmentObject var authViewModel: AuthViewModel
    @State private var selectedTab = 0
    
    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView()
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(0)
            
            ProfileView()
                .tabItem {
                    Label("Profile", systemImage: "person.circle.fill")
                }
                .tag(1)
            
            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
                .tag(2)
        }
    }
}

// Placeholder for HomeView (Week 3-4: Room management)
struct HomeView: View {
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                Image(systemName: "waveform.badge.mic")
                    .font(.system(size: 80))
                    .foregroundColor(.blue)
                
                Text("Welcome to LiveTranslator")
                    .font(.title)
                    .fontWeight(.bold)
                
                Text("Real-time translation for everyone")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                VStack(spacing: 12) {
                    Text("Coming in Week 3-4:")
                        .font(.headline)
                        .padding(.top, 20)
                    
                    FeatureRow(icon: "qrcode", text: "Create & Join Rooms")
                    FeatureRow(icon: "mic.fill", text: "Essential Mode (Apple STT/MT)")
                    FeatureRow(icon: "person.2.fill", text: "Guest Sessions")
                }
                .padding()
                
                Spacer()
            }
            .padding()
            .navigationTitle("Home")
        }
    }
}

struct FeatureRow: View {
    let icon: String
    let text: String
    
    var body: some View {
        HStack {
            Image(systemName: icon)
                .frame(width: 30)
                .foregroundColor(.blue)
            Text(text)
                .font(.callout)
            Spacer()
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
            .environmentObject(AuthViewModel())
    }
}
