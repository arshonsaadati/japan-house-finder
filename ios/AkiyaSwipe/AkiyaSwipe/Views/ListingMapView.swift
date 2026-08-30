import SwiftUI
import MapKit

/// Map section for the profile sheet: pin (or approximate circle) + open in Apple Maps.
struct ListingMapView: View {
    let listing: Listing
    @EnvironmentObject var geocoder: Geocoder
    @State private var position: MapCameraPosition = .automatic

    var body: some View {
        let place = geocoder.place(for: listing)
        VStack(alignment: .leading, spacing: 6) {
            if let p = place {
                let coord = CLLocationCoordinate2D(latitude: p.lat, longitude: p.lng)
                Map(position: $position, interactionModes: [.pan, .zoom]) {
                    if p.approximate {
                        MapCircle(center: coord, radius: 2500)
                            .foregroundStyle(.orange.opacity(0.2)).stroke(.orange, lineWidth: 2)
                    } else {
                        Marker(listing.town ?? "Listing", systemImage: "house.fill", coordinate: coord).tint(.red)
                    }
                }
                .frame(height: 220)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .onAppear {
                    position = .region(MKCoordinateRegion(center: coord,
                        latitudinalMeters: p.approximate ? 12_000 : 1_500,
                        longitudinalMeters: p.approximate ? 12_000 : 1_500))
                }
                HStack {
                    if p.approximate {
                        Label(listing.hasStreetAddress ? "Approximate — exact block not in the map index" : "Town-level only — source gives no street address", systemImage: "questionmark.circle")
                            .font(.caption).foregroundStyle(.orange)
                    } else {
                        Text(String(format: "%.5f, %.5f", p.lat, p.lng)).font(.caption.monospacedDigit())
                            .foregroundStyle(.secondary).textSelection(.enabled)
                    }
                    Spacer()
                    Button {
                        let item = MKMapItem(placemark: MKPlacemark(coordinate: coord))
                        item.name = listing.address ?? listing.displayTitle
                        item.openInMaps()
                    } label: { Label("Maps", systemImage: "arrow.triangle.turn.up.right.diamond") }
                    .font(.caption).buttonStyle(.bordered)
                }
            } else if listing.geocodeQuery == nil || geocoder.failed.contains(listing.id) {
                Label("Location unavailable — couldn't geocode \"\(listing.address ?? listing.town ?? "")\"", systemImage: "mappin.slash")
                    .font(.caption).foregroundStyle(.secondary)
            } else {
                HStack { ProgressView(); Text("Locating…").font(.caption).foregroundStyle(.secondary) }
                    .task { await geocoder.resolve(listing) }
            }
        }
    }
}
