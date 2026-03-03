//
//  SettingsView.swift
//  LiveTranslator
//
//  Feature ID 10: iOS Core Setup (Week 1-2)
//  App settings (placeholder for Week 3-4)
//

import SwiftUI

struct SettingsView: View {
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("App Settings")) {
                    Text("Settings will be available in Week 3-4")
                        .foregroundColor(.secondary)
                }
                
                Section(header: Text("About")) {
                    LabeledContent("Version", value: "1.0.0 (Week 1-2)")
                    LabeledContent("Build", value: "iOS Core Setup")
                }
            }
            .navigationTitle("Settings")
        }
    }
}

struct SettingsView_Previews: PreviewProvider {
    static var previews: some View {
        SettingsView()
    }
}
