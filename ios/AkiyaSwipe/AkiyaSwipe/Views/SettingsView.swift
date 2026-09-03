import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var service: ListingService
    @EnvironmentObject var store: SwipeStore
    @AppStorage(ListingService.serverKey) private var server = ""
    @AppStorage("showRejects") private var showRejects = false
    @AppStorage("verdictOrder") private var verdictOrder = true
    @AppStorage(MatchService.nameKey) private var userName = ""
    @EnvironmentObject var matches: MatchService

    var body: some View {
        NavigationStack {
            Form {
                Section("Server (`akiya serve`)") {
                    TextField(ListingService.defaultServer, text: $server)
                        .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button("Reload listings") { Task { await service.load() } }
                    LabeledContent("Loaded from", value: service.origin)
                    LabeledContent("Listings", value: "\(service.listings.count)")
                    if let e = service.error { Text(e).font(.caption).foregroundStyle(.red) }
                    Text("Blank = the Pi (public HTTPS via Tailscale Funnel, app token required). Enter “-” to use only the bundled snapshot.").font(.caption).foregroundStyle(.secondary)
                }
                Section("Matches") {
                    TextField("Your name", text: $userName)
                    if let e = matches.lastError { Text(e).font(.caption).foregroundStyle(.red) }
                    Text("Your likes (just the listing ids and this name) sync to the Pi so mutual likes show in Matches. Everything else stays on-device.")
                        .font(.caption).foregroundStyle(.secondary)
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
