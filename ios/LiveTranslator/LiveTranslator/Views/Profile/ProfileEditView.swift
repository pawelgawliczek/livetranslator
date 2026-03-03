//
//  ProfileEditView.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  Edit user profile (placeholder for Week 3-4)
//

import SwiftUI

struct ProfileEditView: View {
    let user: User
    @Environment(\.presentationMode) var presentationMode
    
    @State private var displayName: String
    @State private var preferredLang: String
    
    init(user: User) {
        self.user = user
        _displayName = State(initialValue: user.displayName)
        _preferredLang = State(initialValue: user.preferredLang)
    }
    
    var body: some View {
        Form {
            Section(header: Text("Profile Information")) {
                TextField("Display Name", text: $displayName)
                
                Picker("Preferred Language", selection: $preferredLang) {
                    Text("English").tag("en")
                    Text("Spanish").tag("es")
                    Text("French").tag("fr")
                    Text("German").tag("de")
                    Text("Polish").tag("pl")
                    Text("Arabic").tag("ar")
                }
            }
            
            Section {
                Button("Save Changes") {
                    // TODO: Implement profile update API call in Week 3-4
                    // For now, just dismiss
                    presentationMode.wrappedValue.dismiss()
                }
                .disabled(displayName.isEmpty)
                
                Button("Cancel", role: .cancel) {
                    presentationMode.wrappedValue.dismiss()
                }
            }
        }
        .navigationTitle("Edit Profile")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct ProfileEditView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            ProfileEditView(user: User(
                id: 1,
                email: "test@example.com",
                displayName: "Test User",
                preferredLang: "en",
                isAdmin: false,
                createdAt: Date()
            ))
        }
    }
}
