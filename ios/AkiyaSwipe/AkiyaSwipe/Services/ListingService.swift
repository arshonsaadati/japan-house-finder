import Foundation

/// Loads listings from `akiya serve` if a base URL is configured and reachable,
/// otherwise from the bundled snapshot (Resources/listings.json).
@MainActor
final class ListingService: ObservableObject {
    @Published var listings: [Listing] = []
    @Published var origin: String = "bundled snapshot"
    @Published var error: String?
    @Published var loading = false

    static let serverKey = "serverBaseURL"

    var baseURL: URL? {
        let s = UserDefaults.standard.string(forKey: Self.serverKey)?.trimmingCharacters(in: .whitespaces) ?? ""
        return s.isEmpty ? nil : URL(string: s)
    }

    func load() async {
        loading = true; defer { loading = false }
        error = nil
        if let base = baseURL {
            do {
                let (data, resp) = try await URLSession.shared.data(from: base.appendingPathComponent("api/listings"))
                guard (resp as? HTTPURLResponse).map({ 200..<300 ~= $0.statusCode }) ?? true else {
                    throw URLError(.badServerResponse)
                }
                listings = try JSONDecoder().decode(ListingsPayload.self, from: data).listings
                origin = "server \(base.host ?? base.absoluteString)"
                return
            } catch {
                self.error = "Server unreachable (\(error.localizedDescription)); using bundled snapshot."
            }
        }
        loadBundled()
    }

    func loadBundled() {
        guard let url = Bundle.main.url(forResource: "listings", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let payload = try? JSONDecoder().decode(ListingsPayload.self, from: data) else {
            error = "Bundled listings.json missing or invalid"; return
        }
        listings = payload.listings
        origin = "bundled snapshot"
    }
}
