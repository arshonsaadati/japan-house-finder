import SwiftUI
import Shuffle

/// Drives Shuffle's UIKit `SwipeCardStack` from SwiftUI (buttons + undo).
@MainActor
final class DeckController: ObservableObject {
    weak var stack: SwipeCardStack?
    func swipe(_ dir: SwipeDirection) { stack?.swipe(dir, animated: true) }
    func undo() { stack?.undoLastSwipe(animated: true) }
}

struct CardStackView: UIViewRepresentable {
    let listings: [Listing]
    let baseURL: URL?
    let controller: DeckController
    var onSwipe: (Listing, SwipeDirection) -> Void
    var onUndo: (Listing) -> Void
    var onEmpty: () -> Void

    func makeUIView(context: Context) -> SwipeCardStack {
        let stack = SwipeCardStack()
        stack.cardStackInsets = .zero
        stack.dataSource = context.coordinator
        stack.delegate = context.coordinator
        controller.stack = stack
        return stack
    }

    func updateUIView(_ stack: SwipeCardStack, context: Context) {
        let c = context.coordinator
        c.parent = self
        let ids = listings.map(\.id)
        if ids != c.loadedIDs {
            c.loadedIDs = ids
            c.hosts.removeAll()
            stack.reloadData()
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    final class Coordinator: NSObject, SwipeCardStackDataSource, SwipeCardStackDelegate {
        var parent: CardStackView
        var loadedIDs: [String] = []
        var hosts: [Int: UIHostingController<CardView>] = [:]   // retain hosted SwiftUI content

        init(_ parent: CardStackView) { self.parent = parent }

        func numberOfCards(in cardStack: SwipeCardStack) -> Int { parent.listings.count }

        func cardStack(_ cardStack: SwipeCardStack, cardForIndexAt index: Int) -> SwipeCard {
            let listing = parent.listings[index]
            let card = SwipeCard()
            card.swipeDirections = [.left, .right]
            card.footerHeight = 0
            let host = UIHostingController(rootView: CardView(listing: listing, baseURL: parent.baseURL))
            host.view.backgroundColor = .clear
            hosts[index] = host
            card.content = host.view
            card.setOverlay(Self.overlay("LIKE", color: .systemGreen, rotate: -0.25, leading: true), forDirection: .right)
            card.setOverlay(Self.overlay("NOPE", color: .systemRed, rotate: 0.25, leading: false), forDirection: .left)
            return card
        }

        func cardStack(_ cardStack: SwipeCardStack, didSwipeCardAt index: Int, with direction: SwipeDirection) {
            hosts[index] = nil
            parent.onSwipe(parent.listings[index], direction)
        }
        func cardStack(_ cardStack: SwipeCardStack, didUndoCardAt index: Int, from direction: SwipeDirection) {
            parent.onUndo(parent.listings[index])
        }
        func didSwipeAllCards(_ cardStack: SwipeCardStack) { parent.onEmpty() }

        static func overlay(_ text: String, color: UIColor, rotate: CGFloat, leading: Bool) -> UIView {
            let container = UIView()
            let label = UILabel()
            label.text = text
            label.font = .systemFont(ofSize: 40, weight: .heavy)
            label.textColor = color
            label.layer.borderColor = color.cgColor
            label.layer.borderWidth = 4
            label.layer.cornerRadius = 8
            label.textAlignment = .center
            label.transform = CGAffineTransform(rotationAngle: rotate)
            label.translatesAutoresizingMaskIntoConstraints = false
            container.addSubview(label)
            NSLayoutConstraint.activate([
                label.topAnchor.constraint(equalTo: container.topAnchor, constant: 40),
                label.widthAnchor.constraint(equalToConstant: 150),
                label.heightAnchor.constraint(equalToConstant: 60),
                leading ? label.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: 24)
                        : label.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -24),
            ])
            return container
        }
    }
}
