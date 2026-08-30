import SwiftUI

/// One listing card: tap-through photo pager (photos shrink to fit the card,
/// letterboxed on a dark ground) + a bottom info strip. Tapping the left 30%
/// goes back a photo; anywhere else goes forward.
struct CardView: View {
    let listing: Listing
    let baseURL: URL?
    var onInfo: () -> Void

    @State private var index = 0

    private var photos: [URL] { listing.photoURLs(base: baseURL) }

    var body: some View {
        ZStack {
            Color(white: 0.08)
            photoPager
            VStack {
                pips
                Spacer()
                infoStrip
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(.white.opacity(0.12)))
        .shadow(color: .black.opacity(0.25), radius: 12, y: 6)
    }

    private var photoPager: some View {
        GeometryReader { geo in
            ZStack {
                if photos.isEmpty {
                    VStack(spacing: 8) {
                        Image(systemName: "house").font(.system(size: 48))
                        Text("No photos").font(.footnote)
                    }.foregroundStyle(.secondary)
                } else {
                    // Keep every photo mounted so tapping back/forward is instant once loaded.
                    ForEach(Array(photos.enumerated()), id: \.offset) { i, url in
                        RemotePhoto(url: url)
                            .opacity(i == index ? 1 : 0)
                    }
                }
            }
            .frame(width: geo.size.width, height: geo.size.height)
            .contentShape(Rectangle())
            .onTapGesture { pt in
                guard photos.count > 1 else { return }
                if pt.x < geo.size.width * 0.3 { index = max(0, index - 1) }
                else { index = min(photos.count - 1, index + 1) }
            }
        }
    }

    private var pips: some View {
        HStack(spacing: 4) {
            ForEach(0..<max(photos.count, 1), id: \.self) { i in
                Capsule().fill(i == index ? Color.white : Color.white.opacity(0.35)).frame(height: 3)
            }
        }
        .padding(.horizontal, 12).padding(.top, 10)
        .opacity(photos.count > 1 ? 1 : 0)
    }

    private var infoStrip: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(Fmt.yen(listing.priceYen)).font(.system(size: 30, weight: .heavy, design: .rounded))
                Text(Fmt.usd(listing.priceYen)).font(.subheadline.weight(.semibold)).foregroundStyle(.white.opacity(0.75))
                Spacer(minLength: 4)
                VerdictBadge(verdict: listing.verdict)
            }
            HStack(spacing: 6) {
                Image(systemName: "mappin.and.ellipse").font(.caption)
                Text([listing.town, listing.address].compactMap { $0 }.joined(separator: " · "))
                    .font(.subheadline.weight(.medium)).lineLimit(1)
            }
            // Stats chips — everything the scrape gives us, at a glance.
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    if let v = listing.layout { Chip("square.split.2x2", v) }
                    if let v = listing.buildingM2 { Chip("house", Fmt.m2(v)) }
                    if let v = listing.landM2 { Chip("map", "land " + Fmt.m2(v)) }
                    if let y = listing.buildYear { Chip("calendar", "\(y)" + (listing.ageYears.map { " · \($0)y" } ?? "")) }
                    if let v = listing.yenPerBuildingM2 { Chip("yensign", Fmt.yen(v) + "/m²") }
                    if listing.status != "live" { Chip("exclamationmark.triangle", listing.status, tint: .orange) }
                    if listing.propertyType != "detached" { Chip("building.2", listing.propertyType, tint: .orange) }
                    Chip("photo.on.rectangle", "\(listing.photoCount)")
                    Chip("link", listing.source)
                }
            }
            if !listing.flags.isEmpty {
                Label(listing.flags.joined(separator: " • "), systemImage: "flag.fill")
                    .font(.caption2).foregroundStyle(.yellow).lineLimit(2)
            }
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 14).padding(.top, 10).padding(.bottom, 14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            LinearGradient(colors: [.clear, .black.opacity(0.55), .black.opacity(0.92)],
                           startPoint: .top, endPoint: .bottom)
                .padding(.top, -70)
        )
        .overlay(alignment: .topTrailing) {
            Button(action: onInfo) {
                Image(systemName: "info.circle.fill").font(.system(size: 26))
                    .foregroundStyle(.white, .white.opacity(0.25))
            }
            .buttonStyle(.plain)
            .padding(.trailing, 14).padding(.top, -34)
        }
    }
}

struct Chip: View {
    let icon: String; let text: String; var tint: Color = .white
    init(_ icon: String, _ text: String, tint: Color = .white) { self.icon = icon; self.text = text; self.tint = tint }
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon).font(.system(size: 10, weight: .semibold))
            Text(text).font(.caption2.weight(.semibold))
        }
        .padding(.horizontal, 8).padding(.vertical, 5)
        .background(.white.opacity(0.14), in: Capsule())
        .overlay(Capsule().strokeBorder(.white.opacity(0.18)))
        .foregroundStyle(tint)
        .fixedSize()
    }
}

struct VerdictBadge: View {
    let verdict: String?
    var color: Color {
        switch verdict { case "pass": return .green; case "stretch": return .mint
        case "flagged": return .orange; case "reject": return .red; default: return .gray }
    }
    var body: some View {
        Text((verdict ?? "?").uppercased()).font(.caption2.bold())
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(color.opacity(0.9), in: Capsule()).foregroundStyle(.black)
    }
}

/// Shrink-to-fit image with a blurred fill behind it so letterboxing looks intentional.
struct RemotePhoto: View {
    let url: URL
    var body: some View {
        AsyncImage(url: url, transaction: Transaction(animation: .easeIn(duration: 0.15))) { phase in
            switch phase {
            case .success(let img):
                GeometryReader { g in
                    ZStack {
                        img.resizable().scaledToFill()
                            .frame(width: g.size.width, height: g.size.height)
                            .clipped().blur(radius: 24).opacity(0.5)
                        img.resizable().scaledToFit()
                            .frame(width: g.size.width, height: g.size.height)
                    }
                }
            case .failure:
                VStack(spacing: 6) {
                    Image(systemName: "photo.badge.exclamationmark").font(.largeTitle)
                    Text("photo failed").font(.caption2)
                }.foregroundStyle(.secondary)
            default:
                ProgressView().tint(.white)
            }
        }
    }
}
