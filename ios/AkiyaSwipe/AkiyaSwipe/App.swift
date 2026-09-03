import SwiftUI

@main
struct AkiyaSwipeApp: App {
    @StateObject private var service = ListingService()
    @StateObject private var store = SwipeStore()
    @StateObject private var geocoder = Geocoder()
    @StateObject private var matches = MatchService()

    init() {
        // Photos are re-shown constantly while tapping through cards; cache generously.
        URLCache.shared = URLCache(memoryCapacity: 64 << 20, diskCapacity: 512 << 20)
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(service)
                .environmentObject(store)
                .environmentObject(geocoder)
                .environmentObject(matches)
        }
    }
}

struct RootView: View {
    @EnvironmentObject var service: ListingService
    @EnvironmentObject var store: SwipeStore
    @EnvironmentObject var matches: MatchService
    @AppStorage(MatchService.nameKey) private var userName = ""
    @State private var askName = false
    @State private var draftName = ""

    var body: some View {
        TabView {
            DeckView().tabItem { Label("Swipe", systemImage: "rectangle.stack") }
            MatchesView().tabItem { Label("Matches", systemImage: "heart.text.square") }
                .badge(matches.matches(myLikes: store.likes.map(\.id)).count)
            LikesView(kind: .likes).tabItem { Label("Likes", systemImage: "heart.fill") }
                .badge(store.likes.count)
            LikesView(kind: .dislikes).tabItem { Label("Passed", systemImage: "xmark.circle") }
            SettingsView().tabItem { Label("Settings", systemImage: "gear") }
        }
        .task {
            await service.load()
            if userName.isEmpty { askName = true }
            await matches.push(myLikes: store.likes.map(\.id), base: service.baseURL)
        }
        .onReceive(store.$likes) { likes in
            // Fire-and-forget: keep the server copy in step with every like/unlike.
            Task { await matches.push(myLikes: likes.map(\.id), base: service.baseURL) }
        }
        .alert("What's your name?", isPresented: $askName) {
            TextField("e.g. Arshon", text: $draftName)
            Button("Save") { userName = draftName.trimmingCharacters(in: .whitespaces) }
            Button("Later", role: .cancel) {}
        } message: {
            Text("Shown to the other users when you both like the same house.")
        }
    }
}
