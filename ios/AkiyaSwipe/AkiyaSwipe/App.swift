import SwiftUI

@main
struct AkiyaSwipeApp: App {
    @StateObject private var service = ListingService()
    @StateObject private var store = SwipeStore()

    init() {
        // Photos are re-shown constantly while tapping through cards; cache generously.
        URLCache.shared = URLCache(memoryCapacity: 64 << 20, diskCapacity: 512 << 20)
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(service)
                .environmentObject(store)
        }
    }
}

struct RootView: View {
    @EnvironmentObject var service: ListingService
    @EnvironmentObject var store: SwipeStore

    var body: some View {
        TabView {
            DeckView().tabItem { Label("Swipe", systemImage: "rectangle.stack") }
            LikesView(kind: .likes).tabItem { Label("Likes", systemImage: "heart.fill") }
                .badge(store.likes.count)
            LikesView(kind: .dislikes).tabItem { Label("Passed", systemImage: "xmark.circle") }
            SettingsView().tabItem { Label("Settings", systemImage: "gear") }
        }
        .task { await service.load() }
    }
}
