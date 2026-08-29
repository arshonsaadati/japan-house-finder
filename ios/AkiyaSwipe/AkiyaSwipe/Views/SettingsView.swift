import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var service: ListingService
    @EnvironmentObject var store: SwipeStore
    @AppStorage(ListingService.serverKey) private var server = ""
    @AppStorage("showRejects") private var showRejects = false
    @AppStorage("verdictOrder") private var verdictOrder = true

    var body: some View {
        NavigationStack {
            Form {
                Section("Server (`akiya serve`)") {
                    TextField("http://192.168.1.10:8787", text: $server)
                        .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button("Reload listings") { Task { await service.load() } }
                    LabeledContent("Loaded from", value: service.origin)
                    LabeledContent("Listings", value: "\(service.listings.count)")
                    if let e = service.error { Text(e).font(.caption).foregroundStyle(.red) }
                    Text("Leave blank to use the snapshot bundled with the app.").font(.caption).foregroundStyle(.secondary)
                }
                Section("Deck") {
                    Toggle("Include rejected listings", isOn: $showRejects)
                    Toggle("Buyable first (pass → stretch → flagged)", isOn: $verdictOrder)
                }
                Section("Local data") {
                    LabeledContent("Likes", value: "\(store.likes.count)")
                    LabeledContent("Passed", value: "\(store.dislikes.count)")
                    Button("Forget all passed (re-show them)", role: .destructive) { store.clearDislikes() }
                    Text("Likes and passes are stored only on this device.").font(.caption).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
        }
    }
}
