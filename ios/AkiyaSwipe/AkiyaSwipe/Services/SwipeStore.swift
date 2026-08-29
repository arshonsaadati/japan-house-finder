import Foundation

/// Local-only record of likes/dislikes. Stores full listing snapshots so the
/// Likes list keeps working even after a listing vanishes from the scrape.
/// Persisted as JSON in the app's Documents directory — never leaves the device.
@MainActor
final class SwipeStore: ObservableObject {
    struct Entry: Codable, Identifiable {
        var listing: Listing
        var at: Date
        var id: String { listing.id }
    }
    private struct Disk: Codable { var likes: [Entry]; var dislikes: [Entry] }

    @Published private(set) var likes: [Entry] = []
    @Published private(set) var dislikes: [Entry] = []

    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return dir.appendingPathComponent("swipes.json")
    }()

    init() { load() }

    var seenIDs: Set<String> { Set(likes.map(\.id)).union(dislikes.map(\.id)) }
    func isLiked(_ l: Listing) -> Bool { likes.contains { $0.id == l.id } }

    func like(_ l: Listing) {
        remove(l.id)
        likes.insert(Entry(listing: l, at: Date()), at: 0)
        save()
    }
    func dislike(_ l: Listing) {
        remove(l.id)
        dislikes.insert(Entry(listing: l, at: Date()), at: 0)
        save()
    }
    /// Forget a decision (undo / "show me again").
    func forget(_ id: String) { remove(id); save() }

    func clearDislikes() { dislikes.removeAll(); save() }

    private func remove(_ id: String) {
        likes.removeAll { $0.id == id }
        dislikes.removeAll { $0.id == id }
    }

    private func load() {
        guard let data = try? Data(contentsOf: fileURL),
              let d = try? JSONDecoder().decode(Disk.self, from: data) else { return }
        likes = d.likes; dislikes = d.dislikes
    }
    private func save() {
        let d = Disk(likes: likes, dislikes: dislikes)
        if let data = try? JSONEncoder().encode(d) {
            try? data.write(to: fileURL, options: .atomic)
        }
    }
}
