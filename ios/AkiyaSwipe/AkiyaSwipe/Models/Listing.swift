import Foundation

/// Mirrors `akiya.models.Listing` (plus the server-added `photos`).
struct Listing: Codable, Identifiable, Hashable {
    var source: String
    var sourceId: String
    var url: String
    var title: String = ""
    var town: String?
    var address: String?
    var priceYen: Int?
    var layout: String?
    var buildingM2: Double?
    var landM2: Double?
    var buildYear: Int?
    var propertyType: String = "unknown"
    var status: String = "live"
    var flags: [String] = []
    var imageUrls: [String] = []
    var photos: [String]? = nil
    var raw: [String: JSONValue] = [:]
    var verdict: String?
    var verdictReasons: [String] = []
    var firstSeen: String?
    var lastSeen: String?

    enum CodingKeys: String, CodingKey {
        case source, url, title, town, address, layout, status, flags, raw, verdict, photos
        case sourceId = "source_id"
        case priceYen = "price_yen"
        case buildingM2 = "building_m2"
        case landM2 = "land_m2"
        case buildYear = "build_year"
        case propertyType = "property_type"
        case imageUrls = "image_urls"
        case verdictReasons = "verdict_reasons"
        case firstSeen = "first_seen"
        case lastSeen = "last_seen"
    }

    /// Same key the Python store uses: "source:source_id".
    var id: String { "\(source):\(sourceId)" }

    /// Photo URLs, resolved against the server base for relative `/images/...` paths.
    func photoURLs(base: URL?) -> [URL] {
        (photos ?? imageUrls).compactMap { s in
            if s.hasPrefix("/"), let base { return URL(string: s, relativeTo: base)?.absoluteURL }
            return URL(string: s)
        }
    }

    var sourceURL: URL? { URL(string: url) }

    static func == (a: Listing, b: Listing) -> Bool { a.id == b.id }
    func hash(into h: inout Hasher) { h.combine(id) }
}

struct ListingsPayload: Codable {
    var count: Int?
    var updated: String?
    var listings: [Listing]
}

// MARK: - Formatting helpers

enum Fmt {
    static let usdPerYen = 1.0 / 150.0

    static func yen(_ v: Int?) -> String {
        guard let v else { return "price n/a" }
        if v >= 10_000 { return "¥\(fmtGroup(v / 10_000))万" }
        return "¥\(fmtGroup(v))"
    }
    static func yenFull(_ v: Int?) -> String {
        guard let v else { return "—" }
        return "¥\(fmtGroup(v))"
    }
    static func usd(_ v: Int?) -> String {
        guard let v else { return "" }
        return "~$\(fmtGroup(Int(Double(v) * usdPerYen)))"
    }
    static func m2(_ v: Double?) -> String {
        guard let v else { return "—" }
        return String(format: "%.0f m²", v)
    }
    private static func fmtGroup(_ v: Int) -> String {
        let f = NumberFormatter(); f.numberStyle = .decimal
        return f.string(from: NSNumber(value: v)) ?? String(v)
    }
}

extension Listing {
    var priceLine: String {
        let y = Fmt.yen(priceYen), u = Fmt.usd(priceYen)
        return u.isEmpty ? y : "\(y)  \(u)"
    }
    var specLine: String {
        [layout, buildingM2.map { Fmt.m2($0) }, buildYear.map { "built \($0)" }]
            .compactMap { $0 }.joined(separator: " · ")
    }
    var displayTitle: String {
        let t = title.trimmingCharacters(in: .whitespaces)
        return t.isEmpty ? (address ?? id) : t
    }
    var verdictRank: Int {
        switch verdict { case "pass": return 0; case "stretch": return 1; case "flagged": return 2; default: return 3 }
    }
}
