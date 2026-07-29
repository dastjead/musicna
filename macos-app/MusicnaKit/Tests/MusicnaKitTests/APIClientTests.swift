import XCTest
@testable import MusicnaKit

/// URLProtocol 스텁 — httpx.MockTransport(tui 테스트)와 동일한 목적: 실제 네트워크 없이
/// 요청 형태·응답 파싱을 검증한다.
final class StubURLProtocol: URLProtocol {
    static var handler: ((URLRequest) -> (Int, Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = StubURLProtocol.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badURL))
            return
        }
        let (status, data) = handler(request)
        let response = HTTPURLResponse(
            url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

final class APIClientTests: XCTestCase {
    func makeClient() -> APIClient {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        let session = URLSession(configuration: config)
        return APIClient(baseURL: URL(string: "http://test")!, session: session)
    }

    func testHealthReturnsTrueOn200() async {
        StubURLProtocol.handler = { request in
            XCTAssertEqual(request.url?.path, "/health")
            return (200, #"{"status": "ok"}"#.data(using: .utf8)!)
        }
        let result = await makeClient().health()
        XCTAssertTrue(result)
    }

    func testHealthReturnsFalseOnFailure() async {
        StubURLProtocol.handler = { _ in (500, Data()) }
        let result = await makeClient().health()
        XCTAssertFalse(result)
    }

    func testPlayerStatusReturnsNilWhenNothingPlaying() async throws {
        StubURLProtocol.handler = { request in
            XCTAssertEqual(request.url?.path, "/player/status")
            return (200, "null".data(using: .utf8)!)
        }
        let status = try await makeClient().playerStatus()
        XCTAssertNil(status)
    }

    func testPlayerPlayPostsToCorrectPath() async throws {
        var capturedPath: String?
        var capturedMethod: String?
        StubURLProtocol.handler = { request in
            capturedPath = request.url?.path
            capturedMethod = request.httpMethod
            return (200, #"{"status": "ok"}"#.data(using: .utf8)!)
        }
        try await makeClient().playerPlay()
        XCTAssertEqual(capturedPath, "/player/play")
        XCTAssertEqual(capturedMethod, "POST")
    }

    func testPlayerVolumeSendsPercentQueryParam() async throws {
        var capturedQuery: String?
        StubURLProtocol.handler = { request in
            capturedQuery = request.url?.query
            return (200, #"{"status": "ok"}"#.data(using: .utf8)!)
        }
        try await makeClient().playerVolume(55)
        XCTAssertEqual(capturedQuery, "percent=55")
    }

    func testSystemStatusDecodesResponse() async throws {
        StubURLProtocol.handler = { request in
            XCTAssertEqual(request.url?.path, "/system/status")
            return (200, #"{"spotify_player_daemon": true, "session_capturing": false}"#.data(using: .utf8)!)
        }
        let status = try await makeClient().systemStatus()
        XCTAssertTrue(status.spotifyPlayerDaemon)
    }

    func testTracksDecodesArray() async throws {
        StubURLProtocol.handler = { request in
            XCTAssertEqual(request.url?.path, "/tracks")
            let json = """
            [{"id": 1, "track": {"title": "X", "artist": null, "album": null,
              "duration_s": null, "captured_at": null}, "bpm": null, "key": null,
              "mode": null, "moods": []}]
            """
            return (200, json.data(using: .utf8)!)
        }
        let tracks = try await makeClient().tracks()
        XCTAssertEqual(tracks.count, 1)
        XCTAssertEqual(tracks[0].track.title, "X")
    }

    func testHttpErrorThrows() async {
        StubURLProtocol.handler = { _ in (503, Data()) }
        do {
            try await makeClient().playerPlay()
            XCTFail("expected throw")
        } catch {
            // 503 → 에러가 던져지면 통과
        }
    }
}
