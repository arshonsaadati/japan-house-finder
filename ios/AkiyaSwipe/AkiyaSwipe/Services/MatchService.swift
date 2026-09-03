import Foundation

/// Shares this device's likes with the Pi and pulls everyone else's, so the
/// Matches tab can show listings that two or more people liked. No accounts:
/// a random per-install device id plus a self-chosen display name.
@MainActor
final class MatchService: ObservableObject {
    struct Peer: Codable {
        var name: String
        var likes: [String]
        var updated: String?
    }

    @Published private(set) var peers: [String: Peer] = [:]   // device id -> peer
    @Published private(set) var lastError: String?
    @Published private(set) var syncing = false

    static let nameKey = "matchUserName"

    let deviceID: String = {
        let k = "matchDeviceID"
        if let v = UserDefaults.standard.string(forKey: k) { return v }
        let v = UUID().uuidString
        UserDefaults.standard.set(v, forKey: k)
        return v
    }()

    var userName: String {
        UserDefaults.standard.string(forKey: Self.nameKey)?.trimmingCharacters(in: .whitespaces) ?? ""
    }

    private func request(_ base: URL, path: String) -> URLRequest {
        var req = URLRequest(url: base.appendingPathComponent(path))
        if let t = Secrets.apiToken { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }
        return req
    }

    /// Pull everyone's likes.
    func refresh(base: URL?) async {
        guard let base else { return }
        do {
            let (data, _) = try await URLSession.shared.data(for: request(base, path: "api/likes"))
            peers = try JSONDecoder().decode([String: Peer].self, from: data)
            lastError = nil
        } catch {
            lastError = "match sync: \(error.localizedDescription)"
        }
    }

    /// Push my current like list (full replace — idempotent), then refresh.
    func push(myLikes: [String], base: URL?) async {
        guard let base, !userName.isEmpty else { return }
        syncing = true; defer { syncing = false }
        do {
            var req = request(base, path: "api/likes")
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONEncoder().encode(
                ["device": AnyEncodable(deviceID), "name": AnyEncodable(userName), "likes": AnyEncodable(myLikes)])
            let (data, resp) = try await URLSession.shared.data(for: req)
            guard (resp as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
            peers = try JSONDecoder().decode([String: Peer].self, from: data)
            lastError = nil
        } catch {
            lastError = "match sync: \(error.localizedDescription)"
        }
    }

    /// Listing keys liked by me AND at least one other device, with their names.
    func matches(myLikes: [String]) -> [(key: String, names: [String])] {
        let mine = Set(myLikes)
        var byKey: [String: [String]] = [:]
        for (device, peer) in peers where device != deviceID {
            for k in peer.likes where mine.contains(k) {
                byKey[k, default: []].append(peer.name)
            }
        }
        return byKey.map { ($0.key, $0.value.sorted()) }.sorted { $0.key < $1.key }
    }
}

/// Minimal type-erased Encodable for mixed-value JSON bodies.
struct AnyEncodable: Encodable {
    private let encodeFn: (Encoder) throws -> Void
    init<T: Encodable>(_ v: T) { encodeFn = v.encode }
    func encode(to encoder: Encoder) throws { try encodeFn(encoder) }
}
