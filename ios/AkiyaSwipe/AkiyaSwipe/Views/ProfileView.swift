import SwiftUI

/// Everything the scrape knows about a listing, plus the way to contact the seller
/// (the source page — every source's contact form / agent phone lives there).
struct ProfileView: View {
    let listing: Listing
    @EnvironmentObject var service: ListingService
    @EnvironmentObject var store: SwipeStore
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    var body: some View {
        NavigationStack {
            List {
                Section {
                    PhotoStrip(urls: listing.photoURLs(base: service.baseURL))
                        .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                }
                Section {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack { Text(Fmt.yenFull(listing.priceYen)).font(.title.bold()); Spacer(); VerdictBadge(verdict: listing.verdict) }
                        Text(Fmt.usd(listing.priceYen)).foregroundStyle(.secondary)
                        Text(listing.displayTitle).font(.headline)
                        if let a = listing.address { Text(a).font(.subheadline).textSelection(.enabled) }
                    }
                }
                Section("Contact / source") {
                    if let u = listing.sourceURL {
                        Button { openURL(u) } label: {
                            Label("Open listing on \(listing.source)", systemImage: "safari")
                        }
                        ShareLink(item: u) { Label("Share link", systemImage: "square.and.arrow.up") }
                        Text(u.absoluteString).font(.caption2).foregroundStyle(.secondary).textSelection(.enabled)
                    }
                    row("Source", listing.source); row("Source ID", listing.sourceId)
                }
                Section("Facts") {
                    row("Town", listing.town); row("Layout", listing.layout)
                    row("Building", listing.buildingM2.map(Fmt.m2)); row("Land", listing.landM2.map(Fmt.m2))
                    row("Built", listing.buildYear.map(String.init)); row("Type", listing.propertyType)
                    row("Status", listing.status)
                    row("First seen", listing.firstSeen); row("Last seen", listing.lastSeen)
                }
                if !listing.verdictReasons.isEmpty {
                    Section("Verdict: \(listing.verdict ?? "?")") {
                        ForEach(listing.verdictReasons, id: \.self) { Text($0) }
                    }
                }
                if !listing.flags.isEmpty {
                    Section("Flags") { ForEach(listing.flags, id: \.self) { Text($0).foregroundStyle(.orange) } }
                }
                ForEach(listing.raw.keys.sorted(), id: \.self) { key in
                    let v = listing.raw[key]!
                    let rows = v.rows
                    Section("Raw · \(key)") {
                        if rows.isEmpty { Text(v.display).textSelection(.enabled) }
                        else { ForEach(rows, id: \.0) { row($0.0, $0.1) } }
                    }
                }
            }
            .navigationTitle("Listing")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("Done") { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        store.isLiked(listing) ? store.forget(listing.id) : store.like(listing)
                    } label: {
                        Image(systemName: store.isLiked(listing) ? "heart.fill" : "heart").foregroundStyle(.red)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func row(_ k: String, _ v: String?) -> some View {
        if let v, !v.isEmpty {
            HStack(alignment: .top) {
                Text(k).foregroundStyle(.secondary)
                Spacer()
                Text(v).multilineTextAlignment(.trailing).textSelection(.enabled)
            }.font(.subheadline)
        }
    }
}

struct PhotoStrip: View {
    let urls: [URL]
    var body: some View {
        if urls.isEmpty {
            Text("No photos").foregroundStyle(.secondary).frame(maxWidth: .infinity).padding()
        } else {
            TabView {
                ForEach(urls, id: \.self) { u in RemotePhoto(url: u) }
            }
            .tabViewStyle(.page)
            .frame(height: 260)
            .background(Color(white: 0.08))
        }
    }
}
