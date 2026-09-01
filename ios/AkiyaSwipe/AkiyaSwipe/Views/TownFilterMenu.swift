import SwiftUI

/// Toolbar menu: pick one town or all. Shows a filled icon while active.
struct TownFilterMenu: View {
    @Binding var selection: String
    let towns: [String]

    var body: some View {
        Menu {
            Picker("Town", selection: $selection) {
                Label("All towns", systemImage: "globe.asia.australia").tag("")
                ForEach(towns, id: \.self) { Text($0).tag($0) }
            }
        } label: {
            Image(systemName: selection.isEmpty ? "line.3.horizontal.decrease.circle"
                                                : "line.3.horizontal.decrease.circle.fill")
        }
    }
}
