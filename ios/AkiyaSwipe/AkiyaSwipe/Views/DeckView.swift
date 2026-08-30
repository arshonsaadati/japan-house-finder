import SwiftUI
import Shuffle

struct DeckView: View {
    @EnvironmentObject var service: ListingService
    @EnvironmentObject var store: SwipeStore
    @AppStorage("showRejects") private var showRejects = false
    @AppStorage("verdictOrder") private var verdictOrder = true

    @StateObject private var controller = DeckController()
    @State private var deck: [Listing] = []
    @State private var profile: Listing?
    @State private var finished = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                if service.loading && deck.isEmpty {
                    ProgressView("Loading listings…")
                } else if deck.isEmpty || finished {
                    emptyState
                } else {
                    CardStackView(listings: deck, baseURL: service.baseURL, controller: controller,
                                  onSwipe: { l, dir in dir == .right ? store.like(l) : store.dislike(l) },
                                  onUndo: { l in store.forget(l.id) },
                                  onInfo: { l in profile = l },
                                  onEmpty: { finished = true })
                        .padding(.horizontal, 12)
                    controls
                }
            }
            .padding(.bottom, 8)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    VStack(spacing: 0) {
                        Text("Akiya").font(.headline)
                        Text("\(deck.count) left · \(store.likes.count) liked").font(.caption2.monospacedDigit()).foregroundStyle(.secondary)
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { rebuild() } label: { Image(systemName: "arrow.clockwise") }
                }
            }
            .sheet(item: $profile) { l in ProfileView(listing: l) }
            .onChange(of: service.listings) { _, _ in rebuild() }
            .onChange(of: showRejects) { _, _ in rebuild() }
            .onChange(of: verdictOrder) { _, _ in rebuild() }
            .onAppear { if deck.isEmpty { rebuild() } }
        }
    }

    private var controls: some View {
        HStack(spacing: 28) {
            RoundButton(icon: "arrow.uturn.backward", color: .gray, size: 48) { controller.undo() }
            RoundButton(icon: "xmark", color: .red, size: 64) { controller.swipe(.left) }
            RoundButton(icon: "heart.fill", color: .green, size: 64) { controller.swipe(.right) }
            RoundButton(icon: "info", color: .blue, size: 48) {
                if let top = controller.stack?.topCardIndex, top < deck.count { profile = deck[top] }
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "checkmark.seal").font(.system(size: 56)).foregroundStyle(.green)
            Text("You've seen everything").font(.title3.bold())
            Text("\(store.likes.count) liked · \(store.dislikes.count) passed")
                .foregroundStyle(.secondary)
            if !showRejects {
                Button("Show rejected listings too") { showRejects = true }
            }
            Button("Reload from server") { Task { await service.load(); rebuild() } }
            Spacer()
        }.padding(.top, 60)
    }

    /// Deck = every listing not yet liked/disliked, optionally minus rejects,
    /// buyable-first then cheapest. Computed once per rebuild so a swipe
    /// doesn't churn the UIKit stack.
    private func rebuild() {
        let seen = store.seenIDs
        var d = service.listings.filter { !seen.contains($0.id) && (showRejects || $0.verdict != "reject") }
        if verdictOrder {
            d.sort { ($0.verdictRank, $0.priceYen ?? .max) < ($1.verdictRank, $1.priceYen ?? .max) }
        } else {
            d.sort { ($0.priceYen ?? .max) < ($1.priceYen ?? .max) }
        }
        deck = d
        finished = d.isEmpty
    }
}

struct RoundButton: View {
    let icon: String; let color: Color; let size: CGFloat; let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: icon).font(.system(size: size * 0.4, weight: .bold))
                .foregroundStyle(color)
                .frame(width: size, height: size)
                .background(Circle().fill(.background).shadow(color: .black.opacity(0.2), radius: 6, y: 3))
        }
    }
}
