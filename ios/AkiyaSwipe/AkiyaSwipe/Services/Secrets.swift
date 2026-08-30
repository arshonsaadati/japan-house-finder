import Foundation

/// Bundled secrets (Resources/Secrets.plist — gitignored; see Secrets.example.plist).
enum Secrets {
    static let apiToken: String? = {
        guard let url = Bundle.main.url(forResource: "Secrets", withExtension: "plist"),
              let d = NSDictionary(contentsOf: url),
              let t = d["AKIYA_API_TOKEN"] as? String, !t.isEmpty, !t.hasPrefix("PASTE") else { return nil }
        return t
    }()
}
