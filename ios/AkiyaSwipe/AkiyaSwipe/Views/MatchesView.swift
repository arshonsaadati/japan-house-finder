import SwiftUI

struct MatchesView: View {
    @EnvironmentObject var store: SwipeStore
    @EnvironmentObject var service: ListingService
    @EnvironmentObject var matches: MatchService
    @State private var selected: Listing?

    private var rows: [(listing: Listing, names: [String])] {
        matches.matches(myLikes: store.likes.map(\.id)).compactMap { m in
            resolve(m.key).map { ($0, m.names) }
        }
    }

    /// Prefer the live listing; fall back to the liked snapshot.
    private func resolve(_ key: String) -> Listing? {
        service.listings.first { $0.id == key } ?? store.likes.first { $0.id == key }?.listing
    }

    var body: some View {
        NavigationStack {
            Group {
                if matches.userName.isEmpty {
                    ContentUnavailableView("Set your name first", systemImage: "person.crop.circle.badge.questionmark",
                                           description: Text("Matches need a name so others know who liked what. Set it in Settings."))
                } else if rows.isEmpty {
                    ContentUnavailableView("No matches yet", systemImage: "heart.text.square",
                                           description: Text("When you and someone else both like a listing, it shows up here."))
                } else {
                    List(rows, id: \.listing.id) { row in
                        Button { selected = row.listing } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                ListingRow(listing: row.listing, baseURL: service.baseURL)
                                Label("You + \(row.names.joined(separator: ", "))", systemImage: "heart.fill")
                                    .font(.caption.bold()).foregroundStyle(.pink)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .navigationTitle("Matches")
            .toolbar {
                Button { Task { await matches.refresh(base: service.baseURL) } } label: {
                    Image(systemName: "arrow.clockwise")
                }
            }
            .refreshable { await matches.refresh(base: service.baseURL) }
            .task { await matches.refresh(base: service.baseURL) }
            .sheet(item: $selected) { ProfileView(listing: $0) }
        }
    }
}
