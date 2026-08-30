import Foundation

/// Loads listings from `akiya serve` if a base URL is configured and reachable,
/// otherwise from the bundled snapshot (Resources/listings.json).
enum ServerError: LocalizedError {
    case unauthorized
    var errorDescription: String? { "server rejected the app token (401) — check Secrets.plist" }
}

@MainActor
final class ListingService: ObservableObject {
    @Published var listings: [Listing] = []
    @Published var origin: String = "bundled snapshot"
    @Published var error: String?
    @Published var loading = false

    static let serverKey = "serverBaseURL"
    /// The Pi over Tailscale (HTTPS via `tailscale serve`; only reachable from a tailnet the Pi is shared into).
    static let defaultServer = "https://raspberrypi.tail087d97.ts.net"

    var baseURL: URL? {
        let s = UserDefaults.standard.string(forKey: Self.serverKey)?.trimmingCharacters(in: .whitespaces) ?? ""
        if s == "-" { return nil }                       // explicit "bundled only"
        return URL(string: s.isEmpty ? Self.defaultServer : s)
    }

    func load() async {
        loading = true; defer { loading = false }
        error = nil
        if let base = baseURL {
            do {
                var req = URLRequest(url: base.appendingPathComponent("api/listings"))
                if let t = Secrets.apiToken { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }
                let (data, resp) = try await URLSession.shared.data(for: req)
                if let code = (resp as? HTTPURLResponse)?.statusCode {
                    if code == 401 { throw ServerError.unauthorized }
                    guard 200..<300 ~= code else { throw URLError(.badServerResponse) }
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

    /// Freshest copy of a listing (a like/pass snapshot may predate newer scrape fields).
    func live(_ l: Listing) -> Listing { listings.first { $0.id == l.id } ?? l }

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
