import Foundation
import CoreLocation

/// Resolves a listing to a coordinate: scrape-provided lat/lng first, else an
/// on-device CLGeocoder lookup of the Japanese address (cached to disk so each
/// listing is geocoded once — CLGeocoder is rate-limited).
@MainActor
final class Geocoder: ObservableObject {
    struct Place: Codable, Equatable {
        var lat: Double
        var lng: Double
        var approximate: Bool   // true when only the town was known
    }

    @Published private(set) var cache: [String: Place] = [:]
    @Published private(set) var failed: Set<String> = []
    private let geocoder = CLGeocoder()
    private var inflight: Set<String> = []
    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        return dir.appendingPathComponent("geocode.json")
    }()

    init() {
        if let d = try? Data(contentsOf: fileURL), let c = try? JSONDecoder().decode([String: Place].self, from: d) {
            cache = c
        }
    }

    func place(for l: Listing) -> Place? {
        if let lat = l.lat, let lng = l.lng { return Place(lat: lat, lng: lng, approximate: false) }
        return cache[l.id]
    }

    func resolve(_ l: Listing) async {
        guard place(for: l) == nil, !inflight.contains(l.id), !failed.contains(l.id) else { return }
        let candidates = l.geocodeCandidates
        guard !candidates.isEmpty else { failed.insert(l.id); return }
        inflight.insert(l.id); defer { inflight.remove(l.id) }
        for (i, q) in candidates.enumerated() {
            if let c = try? await geocoder.geocodeAddressString(q, in: nil, preferredLocale: Locale(identifier: "ja_JP"))
                .first?.location?.coordinate {
                // Only the last candidate (town) counts as approximate.
                let approx = !l.hasStreetAddress || i == candidates.count - 1
                cache[l.id] = Place(lat: c.latitude, lng: c.longitude, approximate: approx)
                if let d = try? JSONEncoder().encode(cache) { try? d.write(to: fileURL, options: .atomic) }
                return
            }
        }
        failed.insert(l.id)
    }
}
