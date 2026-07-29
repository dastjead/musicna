import XCTest
@testable import MusicnaKit

/// 실제 서버 없이 메시지 시퀀스를 재생하는 가짜 WebSocket — 소진되면 정상 종료(에러 아님)를
/// 시뮬레이션한다. Phase 8 TUI의 _FakeWebSocket과 동일한 목적.
final class FakeWebSocket: WebSocketConnecting {
    private var messages: [String]
    private(set) var cancelCallCount = 0

    init(messages: [String]) { self.messages = messages }

    func receive() async throws -> String {
        guard !messages.isEmpty else {
            throw URLError(.networkConnectionLost) // 스트림 종료를 에러로 표현(URLSessionWebSocketTask와 동일)
        }
        return messages.removeFirst()
    }

    func cancel() { cancelCallCount += 1 }
}

final class LiveEventClientTests: XCTestCase {
    func testEmitsDecodedEventsInOrder() async {
        let messages = [
            #"{"type": "track_started", "track": {"title": "X", "artist": null, "album": null, "duration_s": null, "captured_at": null}}"#,
            #"{"type": "chord", "chord": "C", "start_s": 0.0, "confidence": null}"#,
        ]
        let fake = FakeWebSocket(messages: messages)
        let client = LiveEventClient(
            url: URL(string: "ws://test/ws/live")!,
            connect: { _ in fake },
            reconnectDelay: .seconds(999) // 재연결이 테스트 시간 내에 안 일어나도록 크게
        )

        var received: [LiveEvent] = []
        for await event in client.events() {
            received.append(event)
            if received.count == 2 { break }
        }

        XCTAssertEqual(received.count, 2)
        guard case .chord(let chord, _, _) = received[1] else {
            return XCTFail("expected .chord")
        }
        XCTAssertEqual(chord, "C")
    }

    func testReconnectDelayAppliesOnCleanStreamEnd() async {
        // 메시지가 바로 소진되는 가짜 연결 — reconnectDelay가 즉시 다음 연결 시도를 막는지 확인.
        // 짧은 딜레이(0.05s)로 설정해 "그 시간 안에는 재연결 시도가 없다"를 검증한다.
        var connectCallCount = 0
        let client = LiveEventClient(
            url: URL(string: "ws://test/ws/live")!,
            connect: { _ in
                connectCallCount += 1
                return FakeWebSocket(messages: [])
            },
            reconnectDelay: .milliseconds(50)
        )

        let task = Task {
            for await _ in client.events() { /* 소비만 */ }
        }
        try? await Task.sleep(for: .milliseconds(10))
        // 첫 연결 직후, 스트림이 바로 끝났어도 딜레이(50ms)가 지나기 전에는 재연결이 없어야 한다
        XCTAssertEqual(connectCallCount, 1)
        try? await Task.sleep(for: .milliseconds(100))
        // 딜레이가 지나면 재연결이 최소 한 번은 더 일어나야 한다(busy loop였다면 훨씬 많았을 것)
        XCTAssertGreaterThanOrEqual(connectCallCount, 2)
        XCTAssertLessThan(connectCallCount, 10) // busy loop 회귀 방지 — 짧은 시간 안에 수십 번 재연결되면 안 됨
        task.cancel()
    }
}
