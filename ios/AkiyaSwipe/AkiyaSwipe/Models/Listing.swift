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
    var lat: Double?
    var lng: Double?
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
        case source, url, title, town, address, layout, status, flags, raw, verdict, photos, lat, lng
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

    /// Best text to geocode when the scrape has no coordinates. Street-level
    /// for SUUMO/HOME'S/blogspot; only "Town, Hokkaido" for akiyajapan.
    var geocodeQuery: String? { geocodeCandidates.first }

    /// Progressively coarser queries: full address → without block numbers
    /// (番地) → without chōme → town. CLGeocoder often has no entry for
    /// Hokkaido block numbers but resolves the chōme/district fine.
    var geocodeCandidates: [String] {
        var out: [String] = []
        if let a = address?.replacingOccurrences(of: " ", with: ""), !a.isEmpty {
            let full = a.hasPrefix("北海道") ? a : "北海道" + a
            out.append(full)
            // strip trailing "11-1" / "３１番１１４" style block numbers
            let noBlock = full.replacingOccurrences(of: #"[\d０-９]+([-‐−ー][\d０-９]+)*(番地?|号)?([\d０-９]+)?$"#, with: "", options: .regularExpression)
            if noBlock != full, noBlock.count > 3 { out.append(noBlock) }
            // strip a trailing chōme too
            let noChome = noBlock.replacingOccurrences(of: #"[\d０-９]+丁目$"#, with: "", options: .regularExpression)
            if noChome != noBlock, noChome.count > 3 { out.append(noChome) }
        }
        if let t = town { out.append("\(t), Hokkaido, Japan") }
        return out
    }
    var hasStreetAddress: Bool { !(address ?? "").isEmpty }

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
    var yenPerBuildingM2: Int? {
        guard let p = priceYen, let m = buildingM2, m > 0 else { return nil }
        return Int(Double(p) / m)
    }
    var yenPerLandM2: Int? {
        guard let p = priceYen, let m = landM2, m > 0 else { return nil }
        return Int(Double(p) / m)
    }
    var ageYears: Int? { buildYear.map { Calendar.current.component(.year, from: Date()) - $0 } }
    var photoCount: Int { (photos ?? imageUrls).count }
    var verdictRank: Int {
        switch verdict { case "pass": return 0; case "stretch": return 1; case "flagged": return 2; default: return 3 }
    }
}
