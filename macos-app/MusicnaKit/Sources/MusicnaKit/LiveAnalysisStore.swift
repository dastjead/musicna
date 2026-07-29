import Foundation

@MainActor
public final class LiveAnalysisStore: ObservableObject {
    @Published public private(set) var currentChord: String?
    @Published public private(set) var chordHistory: [String] = []
    @Published public private(set) var activeNoteCount: Int = 0
    @Published public private(set) var isConnected: Bool = false

    private let liveEventClient: LiveEventClient
    private var activeNotes: Set<Int> = []
    private let historyLimit = 8

    public init(liveEventClient: LiveEventClient) {
        self.liveEventClient = liveEventClient
    }

    public func start() {
        Task {
            for await event in liveEventClient.events() {
                handle(event)
            }
        }
    }

    private func handle(_ event: LiveEvent) {
        isConnected = true
        switch event {
        case .trackStarted:
            currentChord = nil
            chordHistory = []
            activeNotes = []
        case .noteOn(let index, _, _, _):
            activeNotes.insert(index)
        case .noteOff(let index, _):
            activeNotes.remove(index)
        case .chord(let chord, _, _):
            if let current = currentChord {
                chordHistory.append(current)
                chordHistory = Array(chordHistory.suffix(historyLimit))
            }
            currentChord = chord
        case .trackEnded:
            activeNotes = []
        case .progress:
            break
        }
        activeNoteCount = activeNotes.count
    }
}
