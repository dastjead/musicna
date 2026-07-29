import XCTest
@testable import MusicnaKit

@MainActor
final class LibraryStoreTests: XCTestCase {
    func testRefreshSkipsMalformedItemsInsteadOfFailingEntirely() async {
        // "id" 필드가 없는 항목 1개 + 정상 항목 1개 — 배열 통짜 디코딩이면 전체가 실패하지만,
        // LibraryStore는 항목 단위로 관용적이어야 한다(Phase 8 최종 리뷰의 KeyError 방지 교훈).
        StubURLProtocol.handler = { request in
            let json = """
            [
              {"not_a_valid_track": true},
              {"id": 2, "track": {"title": "Good", "artist": null, "album": null,
                "duration_s": null, "captured_at": null}, "bpm": null, "key": null,
                "mode": null, "moods": []}
            ]
            """
            return (200, json.data(using: .utf8)!)
        }
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        let client = APIClient(baseURL: URL(string: "http://test")!, session: URLSession(configuration: config))
        let store = LibraryStore(client: client)

        await store.refresh()

        XCTAssertEqual(store.tracks.count, 1)
        XCTAssertEqual(store.tracks.first?.track.title, "Good")
        XCTAssertNil(store.loadError)
    }

    func testRefreshSetsLoadErrorOnNetworkFailure() async {
        StubURLProtocol.handler = { _ in (503, Data()) }
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        let client = APIClient(baseURL: URL(string: "http://test")!, session: URLSession(configuration: config))
        let store = LibraryStore(client: client)

        await store.refresh()

        XCTAssertNotNil(store.loadError)
        XCTAssertEqual(store.tracks, [])
    }
}
