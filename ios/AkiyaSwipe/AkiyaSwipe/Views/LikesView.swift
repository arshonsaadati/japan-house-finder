import SwiftUI

struct LikesView: View {
    enum Kind { case likes, dislikes }
    let kind: Kind
    @EnvironmentObject var store: SwipeStore
    @EnvironmentObject var service: ListingService
    @State private var selected: Listing?
    @State private var townFilter = ""

    private var allEntries: [SwipeStore.Entry] { kind == .likes ? store.likes : store.dislikes }
    private var entries: [SwipeStore.Entry] {
        townFilter.isEmpty ? allEntries : allEntries.filter { $0.listing.town == townFilter }
    }
    private var allTowns: [String] { Array(Set(allEntries.compactMap(\.listing.town))).sorted() }

    var body: some View {
        NavigationStack {
            Group {
                if entries.isEmpty {
                    ContentUnavailableView(
                        townFilter.isEmpty ? (kind == .likes ? "No likes yet" : "Nothing passed yet") : "Nothing in \(townFilter)",
                        systemImage: kind == .likes ? "heart" : "xmark.circle",
                        description: Text(townFilter.isEmpty ? "Swipe right to like, left to pass." : "Change or clear the town filter."))
                } else {
                    List {
                        ForEach(entries) { e in
                            Button { selected = service.live(e.listing) } label: { ListingRow(listing: e.listing, baseURL: service.baseURL) }
                                .buttonStyle(.plain)
                                .swipeActions {
                                    Button(role: .destructive) { store.forget(e.id) } label: {
                                        Label("Forget", systemImage: "arrow.uturn.backward")
                                    }
                                    if kind == .dislikes {
                                        Button { store.like(e.listing) } label: { Label("Like", systemImage: "heart") }.tint(.green)
                                    } else {
                                        Button { store.dislike(e.listing) } label: { Label("Pass", systemImage: "xmark") }.tint(.red)
                                    }
                                }
                        }
                    }
                }
            }
            .navigationTitle(kind == .likes ? "Likes" : "Passed")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    TownFilterMenu(selection: $townFilter, towns: allTowns)
                }
                if kind == .dislikes && !allEntries.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) { Button("Clear all") { store.clearDislikes() } }
                }
            }
            .sheet(item: $selected) { ProfileView(listing: $0) }
        }
    }
}

struct ListingRow: View {
    let listing: Listing
    let baseURL: URL?
    var body: some View {
        HStack(spacing: 12) {
            AsyncImage(url: listing.photoURLs(base: baseURL).first) { img in
                img.resizable().scaledToFill()
            } placeholder: { Color(white: 0.85) }
            .frame(width: 84, height: 64).clipShape(RoundedRectangle(cornerRadius: 8))
            VStack(alignment: .leading, spacing: 3) {
                HStack { Text(listing.priceLine).font(.headline); VerdictBadge(verdict: listing.verdict) }
                Text([listing.town, listing.address ?? listing.displayTitle].compactMap { $0 }.joined(separator: " · "))
                    .font(.subheadline).lineLimit(1)
                Text(listing.specLine).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right").foregroundStyle(.tertiary)
        }
        .contentShape(Rectangle())
    }
}
