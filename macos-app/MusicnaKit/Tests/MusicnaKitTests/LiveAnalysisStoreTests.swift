import XCTest
@testable import MusicnaKit

@MainActor
final class LiveAnalysisStoreTests: XCTestCase {
    func testChordEventUpdatesCurrentAndHistory() async {
        let messages = [
            #"{"type": "track_started", "track": {"title": "X", "artist": null, "album": null, "duration_s": null, "captured_at": null}}"#,
            #"{"type": "chord", "chord": "C", "start_s": 0.0, "confidence": null}"#,
            #"{"type": "chord", "chord": "F", "start_s": 1.0, "confidence": null}"#,
        ]
        let client = LiveEventClient(
            url: URL(string: "ws://test/ws/live")!,
            connect: { _ in FakeWebSocket(messages: messages) },
            reconnectDelay: .seconds(999)
        )
        let store = LiveAnalysisStore(liveEventClient: client)
        store.start()

        // 3개 이벤트가 처리될 시간을 준다(실제 네트워크 없이 즉시 처리되므로 짧아도 충분)
        try? await Task.sleep(for: .milliseconds(50))

        XCTAssertEqual(store.currentChord, "F")
        XCTAssertEqual(store.chordHistory, ["C"])
    }

    func testTrackStartedResetsState() async {
        let messages = [
            #"{"type": "chord", "chord": "G7", "start_s": 0.0, "confidence": null}"#,
            #"{"type": "track_started", "track": {"title": "Y", "artist": null, "album": null, "duration_s": null, "captured_at": null}}"#,
        ]
        let client = LiveEventClient(
            url: URL(string: "ws://test/ws/live")!,
            connect: { _ in FakeWebSocket(messages: messages) },
            reconnectDelay: .seconds(999)
        )
        let store = LiveAnalysisStore(liveEventClient: client)
        store.start()

        try? await Task.sleep(for: .milliseconds(50))

        XCTAssertNil(store.currentChord)
        XCTAssertEqual(store.activeNoteCount, 0)
    }

    func testNoteOnAndOffUpdateActiveCount() async {
        let messages = [
            #"{"type": "note_on", "index": 1, "pitch": 60, "instrument": null, "start_s": 0.0}"#,
            #"{"type": "note_on", "index": 2, "pitch": 64, "instrument": null, "start_s": 0.1}"#,
            #"{"type": "note_off", "index": 1, "end_s": 0.5}"#,
        ]
        let client = LiveEventClient(
            url: URL(string: "ws://test/ws/live")!,
            connect: { _ in FakeWebSocket(messages: messages) },
            reconnectDelay: .seconds(999)
        )
        let store = LiveAnalysisStore(liveEventClient: client)
        store.start()

        try? await Task.sleep(for: .milliseconds(50))

        XCTAssertEqual(store.activeNoteCount, 1)
    }
}
