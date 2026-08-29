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
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(listing.priceLine).font(.title2.bold())
                    VerdictBadge(verdict: listing.verdict)
                }
                Text([listing.town, listing.address].compactMap { $0 }.joined(separator: " · "))
                    .font(.subheadline).lineLimit(1)
                Text(listing.specLine).font(.caption).foregroundStyle(.white.opacity(0.8))
                if !listing.flags.isEmpty {
                    Text(listing.flags.joined(separator: " • ")).font(.caption2)
                        .foregroundStyle(.yellow).lineLimit(2)
                }
            }
            Spacer(minLength: 8)
            Button(action: onInfo) {
                Image(systemName: "info.circle.fill").font(.system(size: 30))
            }
            .buttonStyle(.plain)
        }
        .foregroundStyle(.white)
        .padding(14)
        .background(
            LinearGradient(colors: [.clear, .black.opacity(0.85)], startPoint: .top, endPoint: .bottom)
                .padding(.top, -60)
        )
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
