import Foundation

public protocol WebSocketConnecting {
    func receive() async throws -> String
    func cancel()
}

private class URLSessionWebSocketTaskAdapter: WebSocketConnecting {
    private let task: URLSessionWebSocketTask

    init(_ task: URLSessionWebSocketTask) {
        self.task = task
    }

    func receive() async throws -> String {
        let message = try await task.receive()
        switch message {
        case .string(let text): return text
        case .data(let data): return String(decoding: data, as: UTF8.self)
        @unknown default: return ""
        }
    }

    func cancel() {
        task.cancel()
    }
}

extension URLSessionWebSocketTask {
    public static func connecting(url: URL) -> WebSocketConnecting {
        let task = URLSession.shared.webSocketTask(with: url)
        task.resume()
        return URLSessionWebSocketTaskAdapter(task)
    }
}

public final class LiveEventClient {
    private let url: URL
    private let connect: (URL) -> WebSocketConnecting
    private let reconnectDelay: Duration

    public init(
        url: URL,
        connect: @escaping (URL) -> WebSocketConnecting = URLSessionWebSocketTask.connecting,
        reconnectDelay: Duration = .seconds(2)
    ) {
        self.url = url
        self.connect = connect
        self.reconnectDelay = reconnectDelay
    }

    /// `/ws/live` 이벤트를 무한 스트림으로 방출한다. 연결이 어떤 이유로 끊기든(정상 종료·에러)
    /// 재연결 전 항상 `reconnectDelay`만큼 대기한다 — 그렇지 않으면 즉시 재연결→즉시 종료가
    /// 반복되는 바쁜 루프가 된다(Phase 8 TUI LiveAnalysisWidget에서 실측으로 발견된 버그).
    public func events() -> AsyncStream<LiveEvent> {
        AsyncStream { continuation in
            let task = Task {
                while !Task.isCancelled {
                    let ws = connect(url)
                    loop: while !Task.isCancelled {
                        do {
                            let raw = try await ws.receive()
                            if let data = raw.data(using: .utf8),
                               let event = try? JSONDecoder().decode(LiveEvent.self, from: data) {
                                continuation.yield(event)
                            }
                        } catch {
                            break loop
                        }
                    }
                    ws.cancel()
                    if Task.isCancelled { break }
                    try? await Task.sleep(for: reconnectDelay)
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}
