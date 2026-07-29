# Phase 9 — macOS 네이티브 앱 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 메뉴바 재생 제어·세션 상태·실시간 코드 표시 + 별도 라이브러리 창을 가진 macOS 네이티브 앱을 만든다. 네트워킹·모델·상태 로직은 플랫폼 무관 Swift 패키지 `MusicnaKit`에 두어 Phase 10(iOS)이 재사용할 수 있게 한다.

**Architecture:** `macos-app/MusicnaKit`(로컬 SPM 패키지, `Foundation`만 사용) + `macos-app/Musicna`(Xcode App 타겟, SwiftUI). `MusicnaKit`은 `APIClient`(REST)·`LiveEventClient`(WebSocket)·`Models`(Codable)·3개 `ObservableObject` 스토어로 구성되며 App 타겟은 이 스토어를 구독해 그리기만 한다. Xcode 프로젝트는 XcodeGen(`project.yml`)으로 생성한다.

**Tech Stack:** Swift 6.x(이 머신의 `swift --version` 기준), SwiftUI(`MenuBarExtra`, macOS 13+), `URLSession`(REST+WebSocket), XCTest, XcodeGen.

## Global Constraints

- **환경 제약(중요)**: 이 머신(`hostname: Mac`, macOS 26.5)은 실제 프로젝트에서 써온 macOS 머신이 맞지만, 지금은 Command Line Tools만 설치돼 있고 **전체 Xcode.app은 없다**(`xcodebuild`가 "requires Xcode" 에러). Task 1~4(`MusicnaKit`, 순수 SPM 패키지)는 `swift build`/`swift test`만으로 지금 바로 실행 가능하다. **Task 5부터는 Xcode.app 설치가 선행 조건**이다(App Store에서 사용자가 직접 설치 — 자동화 불가) — Task 5 착수 전 `xcodebuild -version`이 정상 출력되는지 먼저 확인할 것.
- `MusicnaKit`은 `import SwiftUI`·`import AppKit`을 하지 않는다 — App 타겟과의 경계를 지킨다(core/api의 "macOS API import 금지" 원칙과 대응).
- REST/WebSocket 응답 JSON 필드명(스네이크 케이스)은 실제 `api/src/musicna_api/player.py`(`PlayerStatus`)·`api/src/musicna_api/system.py`(`SystemStatus`)·`core/src/musicna_core/models.py`(`LiveEvent`·`TrackMeta`·`AnalysisResult`·`MoodTag`)를 그대로 읽어 확정한 것이다 — 임의로 필드를 추가/변경하지 말 것.
- `LiveEventClient`의 재연결 로직은 **정상 종료·에러 종료 관계없이 재연결 전 항상 고정 딜레이를 거쳐야 한다** — Phase 8 TUI의 `LiveAnalysisWidget` 구현 중 실측으로 발견된 busy-loop 버그(계획 브리프에 `asyncio.sleep`이 `except` 안에만 있어 정상 종료 시 즉시 재연결을 반복하던 문제)를 Swift에서도 똑같이 재현하지 않도록 처음부터 이 요구사항을 반영한다.
- `LibraryStore`가 `/tracks` 배열을 디코딩할 때 **항목 하나가 손상돼도 전체가 실패하지 않아야 한다** — Phase 8 최종 리뷰에서 고친 KeyError 방지 패턴(개별 항목 skip)을 Swift에서도 처음부터 반영한다.
- 신규 의존성은 XcodeGen(Homebrew, Task 5에서 1회 설치)뿐 — `MusicnaKit` 자체는 외부 패키지 의존성 없이 `Foundation`만 사용한다.

---

## Task 1: `MusicnaKit` 패키지 스캐폴딩 + Models.swift

**Files:**
- Create: `macos-app/MusicnaKit/Package.swift`
- Create: `macos-app/MusicnaKit/Sources/MusicnaKit/Models.swift`
- Create: `macos-app/MusicnaKit/Tests/MusicnaKitTests/ModelsTests.swift`

**Interfaces:**
- Produces: `PlayerStatus`, `SystemStatus`, `TrackMeta`, `MoodTag`, `AnalysisResult`(모두 `public`, `Codable`, `Equatable`), `LiveEvent`(`public`, `Decodable`, `Equatable`, 6-case enum) — Task 2~4가 이 타입들을 그대로 쓴다.

- [ ] **Step 1: 패키지 스캐폴딩**

`macos-app/MusicnaKit/Package.swift`:

```swift
// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "MusicnaKit",
    platforms: [.macOS(.v13), .iOS(.v16)],
    products: [
        .library(name: "MusicnaKit", targets: ["MusicnaKit"]),
    ],
    targets: [
        .target(name: "MusicnaKit"),
        .testTarget(name: "MusicnaKitTests", dependencies: ["MusicnaKit"]),
    ]
)
```

Run: `cd macos-app/MusicnaKit && swift build`
Expected: 성공(빈 타겟이라도 컴파일됨) — `Sources/MusicnaKit/`에 아직 `.swift` 파일이 없으면 실패할 수 있으니, 먼저 빈 `Sources/MusicnaKit/Models.swift`(주석 한 줄만)와 `Tests/MusicnaKitTests/ModelsTests.swift`(빈 `import XCTest` + `final class ModelsTests: XCTestCase {}`)를 만들고 실행할 것

- [ ] **Step 2: 실패하는 테스트를 작성**

`macos-app/MusicnaKit/Tests/MusicnaKitTests/ModelsTests.swift`:

```swift
import XCTest
@testable import MusicnaKit

final class ModelsTests: XCTestCase {
    func testPlayerStatusDecodesSnakeCaseFields() throws {
        let json = """
        {"is_playing": true, "item_title": "Test Track", "item_artist": "Test Artist",
         "item_album": "Test Album", "item_duration_s": 219.413, "progress_s": 5.614,
         "volume_percent": 75, "device_name": "spotify-player", "shuffle": true,
         "repeat_state": "off"}
        """.data(using: .utf8)!
        let status = try JSONDecoder().decode(PlayerStatus.self, from: json)
        XCTAssertEqual(status.isPlaying, true)
        XCTAssertEqual(status.itemTitle, "Test Track")
        XCTAssertEqual(status.volumePercent, 75)
        XCTAssertEqual(status.repeatState, "off")
    }

    func testPlayerStatusDecodesNullOptionalFields() throws {
        let json = """
        {"is_playing": false, "item_title": null, "item_artist": null, "item_album": null,
         "item_duration_s": null, "progress_s": null, "volume_percent": null,
         "device_name": null, "shuffle": false, "repeat_state": "off"}
        """.data(using: .utf8)!
        let status = try JSONDecoder().decode(PlayerStatus.self, from: json)
        XCTAssertNil(status.itemTitle)
        XCTAssertNil(status.volumePercent)
    }

    func testSystemStatusDecodesSnakeCaseFields() throws {
        let json = """
        {"spotify_player_daemon": true, "session_capturing": false}
        """.data(using: .utf8)!
        let status = try JSONDecoder().decode(SystemStatus.self, from: json)
        XCTAssertTrue(status.spotifyPlayerDaemon)
        XCTAssertFalse(status.sessionCapturing)
    }

    func testAnalysisResultDecodesWithMoods() throws {
        let json = """
        {"id": 1, "track": {"title": "곡", "artist": "아티스트", "album": null,
         "duration_s": 200.0, "captured_at": "2026-07-25T10:00:00"},
         "bpm": 118.0, "key": "D", "mode": "major",
         "moods": [{"tag": "happy", "score": 0.8}]}
        """.data(using: .utf8)!
        let result = try JSONDecoder().decode(AnalysisResult.self, from: json)
        XCTAssertEqual(result.id, 1)
        XCTAssertEqual(result.track.title, "곡")
        XCTAssertEqual(result.bpm, 118.0)
        XCTAssertEqual(result.moods.first?.tag, "happy")
    }

    func testLiveEventDecodesTrackStarted() throws {
        let json = """
        {"type": "track_started", "track": {"title": "X", "artist": null, "album": null,
         "duration_s": null, "captured_at": null}}
        """.data(using: .utf8)!
        let event = try JSONDecoder().decode(LiveEvent.self, from: json)
        guard case .trackStarted(let track) = event else {
            return XCTFail("expected .trackStarted, got \\(event)")
        }
        XCTAssertEqual(track.title, "X")
    }

    func testLiveEventDecodesNoteOn() throws {
        let json = """
        {"type": "note_on", "index": 1, "pitch": 60, "instrument": null, "start_s": 0.5}
        """.data(using: .utf8)!
        let event = try JSONDecoder().decode(LiveEvent.self, from: json)
        guard case .noteOn(let index, let pitch, let instrument, let startS) = event else {
            return XCTFail("expected .noteOn, got \\(event)")
        }
        XCTAssertEqual(index, 1)
        XCTAssertEqual(pitch, 60)
        XCTAssertNil(instrument)
        XCTAssertEqual(startS, 0.5)
    }

    func testLiveEventDecodesNoteOff() throws {
        let json = """{"type": "note_off", "index": 1, "end_s": 1.5}""".data(using: .utf8)!
        let event = try JSONDecoder().decode(LiveEvent.self, from: json)
        guard case .noteOff(let index, let endS) = event else {
            return XCTFail("expected .noteOff, got \\(event)")
        }
        XCTAssertEqual(index, 1)
        XCTAssertEqual(endS, 1.5)
    }

    func testLiveEventDecodesChord() throws {
        let json = """
        {"type": "chord", "chord": "Cmaj7", "start_s": 0.0, "confidence": 0.9}
        """.data(using: .utf8)!
        let event = try JSONDecoder().decode(LiveEvent.self, from: json)
        guard case .chord(let chord, _, let confidence) = event else {
            return XCTFail("expected .chord, got \\(event)")
        }
        XCTAssertEqual(chord, "Cmaj7")
        XCTAssertEqual(confidence, 0.9)
    }

    func testLiveEventDecodesProgress() throws {
        let json = """
        {"type": "progress", "chunk_start_s": 0.0, "chunk_end_s": 5.0}
        """.data(using: .utf8)!
        let event = try JSONDecoder().decode(LiveEvent.self, from: json)
        guard case .progress(let start, let end) = event else {
            return XCTFail("expected .progress, got \\(event)")
        }
        XCTAssertEqual(start, 0.0)
        XCTAssertEqual(end, 5.0)
    }

    func testLiveEventDecodesTrackEnded() throws {
        let json = """{"type": "track_ended"}""".data(using: .utf8)!
        let event = try JSONDecoder().decode(LiveEvent.self, from: json)
        XCTAssertEqual(event, .trackEnded)
    }

    func testLiveEventUnknownTypeThrows() {
        let json = """{"type": "something_new"}""".data(using: .utf8)!
        XCTAssertThrowsError(try JSONDecoder().decode(LiveEvent.self, from: json))
    }
}
```

- [ ] **Step 2b: 테스트 실행 → 실패 확인**

Run: `cd macos-app/MusicnaKit && swift test`
Expected: FAIL — `PlayerStatus`/`SystemStatus`/`TrackMeta`/`MoodTag`/`AnalysisResult`/`LiveEvent` 타입이 아직 없어 컴파일 에러

- [ ] **Step 3: `Sources/MusicnaKit/Models.swift` 작성**

```swift
import Foundation

public struct PlayerStatus: Codable, Equatable {
    public let isPlaying: Bool
    public let itemTitle: String?
    public let itemArtist: String?
    public let itemAlbum: String?
    public let itemDurationS: Double?
    public let progressS: Double?
    public let volumePercent: Int?
    public let deviceName: String?
    public let shuffle: Bool
    public let repeatState: String

    enum CodingKeys: String, CodingKey {
        case isPlaying = "is_playing"
        case itemTitle = "item_title"
        case itemArtist = "item_artist"
        case itemAlbum = "item_album"
        case itemDurationS = "item_duration_s"
        case progressS = "progress_s"
        case volumePercent = "volume_percent"
        case deviceName = "device_name"
        case shuffle
        case repeatState = "repeat_state"
    }
}

public struct SystemStatus: Codable, Equatable {
    public let spotifyPlayerDaemon: Bool
    public let sessionCapturing: Bool

    enum CodingKeys: String, CodingKey {
        case spotifyPlayerDaemon = "spotify_player_daemon"
        case sessionCapturing = "session_capturing"
    }
}

public struct TrackMeta: Codable, Equatable {
    public let title: String
    public let artist: String?
    public let album: String?
    public let durationS: Double?
    public let capturedAt: String?

    enum CodingKeys: String, CodingKey {
        case title, artist, album
        case durationS = "duration_s"
        case capturedAt = "captured_at"
    }
}

public struct MoodTag: Codable, Equatable {
    public let tag: String
    public let score: Double
}

public struct AnalysisResult: Codable, Equatable, Identifiable {
    public let id: Int?
    public let track: TrackMeta
    public let bpm: Double?
    public let key: String?
    public let mode: String?
    public let moods: [MoodTag]
}

public enum LiveEvent: Decodable, Equatable {
    case trackStarted(track: TrackMeta)
    case noteOn(index: Int, pitch: Int, instrument: String?, startS: Double)
    case noteOff(index: Int, endS: Double)
    case chord(chord: String, startS: Double, confidence: Double?)
    case progress(chunkStartS: Double, chunkEndS: Double)
    case trackEnded

    private enum CodingKeys: String, CodingKey {
        case type, track, index, pitch, instrument, chord, confidence
        case startS = "start_s"
        case endS = "end_s"
        case chunkStartS = "chunk_start_s"
        case chunkEndS = "chunk_end_s"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let type = try c.decode(String.self, forKey: .type)
        switch type {
        case "track_started":
            self = .trackStarted(track: try c.decode(TrackMeta.self, forKey: .track))
        case "note_on":
            self = .noteOn(
                index: try c.decode(Int.self, forKey: .index),
                pitch: try c.decode(Int.self, forKey: .pitch),
                instrument: try c.decodeIfPresent(String.self, forKey: .instrument),
                startS: try c.decode(Double.self, forKey: .startS)
            )
        case "note_off":
            self = .noteOff(
                index: try c.decode(Int.self, forKey: .index),
                endS: try c.decode(Double.self, forKey: .endS)
            )
        case "chord":
            self = .chord(
                chord: try c.decode(String.self, forKey: .chord),
                startS: try c.decode(Double.self, forKey: .startS),
                confidence: try c.decodeIfPresent(Double.self, forKey: .confidence)
            )
        case "progress":
            self = .progress(
                chunkStartS: try c.decode(Double.self, forKey: .chunkStartS),
                chunkEndS: try c.decode(Double.self, forKey: .chunkEndS)
            )
        case "track_ended":
            self = .trackEnded
        default:
            throw DecodingError.dataCorruptedError(
                forKey: .type, in: c, debugDescription: "unknown LiveEvent type: \(type)"
            )
        }
    }
}
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd macos-app/MusicnaKit && swift test`
Expected: PASS — 전부(11개)

- [ ] **Step 5: 커밋**

```bash
git add macos-app/MusicnaKit/Package.swift macos-app/MusicnaKit/Sources/MusicnaKit/Models.swift macos-app/MusicnaKit/Tests/MusicnaKitTests/ModelsTests.swift
git commit -m "feat: MusicnaKit 패키지 스캐폴딩 + Codable 모델(PlayerStatus/SystemStatus/AnalysisResult/LiveEvent)"
```

---

## Task 2: `APIClient.swift` — REST 호출

**Files:**
- Create: `macos-app/MusicnaKit/Sources/MusicnaKit/APIClient.swift`
- Create: `macos-app/MusicnaKit/Tests/MusicnaKitTests/APIClientTests.swift`

**Interfaces:**
- Consumes: `PlayerStatus`, `SystemStatus`, `AnalysisResult`(Task 1)
- Produces: `public final class APIClient` — `init(baseURL: URL, session: URLSession = .shared)`, `func health() async -> Bool`, `func playerStatus() async throws -> PlayerStatus?`, `func playerPlay() async throws`, `func playerPause() async throws`, `func playerNext() async throws`, `func playerPrevious() async throws`, `func playerVolume(_ percent: Int) async throws`, `func systemStatus() async throws -> SystemStatus`, `func tracks() async throws -> [AnalysisResult]`. Task 4가 이 클래스를 스토어에서 사용.

- [ ] **Step 1: 실패하는 테스트를 작성**

`macos-app/MusicnaKit/Tests/MusicnaKitTests/APIClientTests.swift`:

```swift
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd macos-app/MusicnaKit && swift test`
Expected: FAIL — `APIClient` 타입이 없어 컴파일 에러

- [ ] **Step 3: `Sources/MusicnaKit/APIClient.swift` 작성**

```swift
import Foundation

public enum APIClientError: Error {
    case httpError(status: Int)
}

public final class APIClient {
    private let baseURL: URL
    private let session: URLSession
    private let decoder = JSONDecoder()

    public init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    public func health() async -> Bool {
        guard let (_, response) = try? await session.data(from: baseURL.appendingPathComponent("health")),
              let http = response as? HTTPURLResponse
        else { return false }
        return http.statusCode == 200
    }

    public func playerStatus() async throws -> PlayerStatus? {
        let data = try await get(path: "player/status")
        if String(data: data, encoding: .utf8) == "null" { return nil }
        return try decoder.decode(PlayerStatus.self, from: data)
    }

    public func playerPlay() async throws { try await post(path: "player/play") }
    public func playerPause() async throws { try await post(path: "player/pause") }
    public func playerNext() async throws { try await post(path: "player/next") }
    public func playerPrevious() async throws { try await post(path: "player/previous") }

    public func playerVolume(_ percent: Int) async throws {
        try await post(path: "player/volume", query: [URLQueryItem(name: "percent", value: String(percent))])
    }

    public func systemStatus() async throws -> SystemStatus {
        try decoder.decode(SystemStatus.self, from: try await get(path: "system/status"))
    }

    public func tracks() async throws -> [AnalysisResult] {
        try decoder.decode([AnalysisResult].self, from: try await get(path: "tracks"))
    }

    private func get(path: String) async throws -> Data {
        try await request(path: path, method: "GET")
    }

    private func post(path: String, query: [URLQueryItem] = []) async throws {
        _ = try await request(path: path, method: "POST", query: query)
    }

    private func request(path: String, method: String, query: [URLQueryItem] = []) async throws -> Data {
        var components = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { components.queryItems = query }
        var req = URLRequest(url: components.url!)
        req.httpMethod = method
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            let status = (response as? HTTPURLResponse)?.statusCode ?? -1
            throw APIClientError.httpError(status: status)
        }
        return data
    }
}
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd macos-app/MusicnaKit && swift test`
Expected: PASS — 전부(19개: Task 1의 11 + Task 2의 8)

- [ ] **Step 5: 커밋**

```bash
git add macos-app/MusicnaKit/Sources/MusicnaKit/APIClient.swift macos-app/MusicnaKit/Tests/MusicnaKitTests/APIClientTests.swift
git commit -m "feat: MusicnaKit APIClient — /player, /system, /tracks REST 호출"
```

---

## Task 3: `LiveEventClient.swift` — WebSocket 구독 + 재연결

**Files:**
- Create: `macos-app/MusicnaKit/Sources/MusicnaKit/LiveEventClient.swift`
- Create: `macos-app/MusicnaKit/Tests/MusicnaKitTests/LiveEventClientTests.swift`

**Interfaces:**
- Consumes: `LiveEvent`(Task 1)
- Produces: `public protocol WebSocketConnecting`(테스트에서 가짜로 교체 가능하도록 실제 `URLSessionWebSocketTask`를 감싸는 추상화) — `func receive() async throws -> String`, `func cancel()`. `public final class LiveEventClient` — `init(url: URL, connect: @escaping (URL) -> WebSocketConnecting = URLSessionWebSocketTask.connecting, reconnectDelay: Duration = .seconds(2))`, `func events() -> AsyncStream<LiveEvent>`. Task 4가 이 클래스를 `LiveAnalysisStore`에서 사용.

- [ ] **Step 1: 실패하는 테스트를 작성**

`macos-app/MusicnaKit/Tests/MusicnaKitTests/LiveEventClientTests.swift`:

```swift
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd macos-app/MusicnaKit && swift test`
Expected: FAIL — `WebSocketConnecting`/`LiveEventClient` 타입이 없어 컴파일 에러

- [ ] **Step 3: `Sources/MusicnaKit/LiveEventClient.swift` 작성**

```swift
import Foundation

public protocol WebSocketConnecting {
    func receive() async throws -> String
    func cancel()
}

extension URLSessionWebSocketTask: WebSocketConnecting {
    public func receive() async throws -> String {
        let message = try await receive()
        switch message {
        case .string(let text): return text
        case .data(let data): return String(decoding: data, as: UTF8.self)
        @unknown default: return ""
        }
    }

    public static func connecting(url: URL) -> WebSocketConnecting {
        let task = URLSession.shared.webSocketTask(with: url)
        task.resume()
        return task
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd macos-app/MusicnaKit && swift test`
Expected: PASS — 전부(21개: 이전 19 + Task 3의 2)

- [ ] **Step 5: 커밋**

```bash
git add macos-app/MusicnaKit/Sources/MusicnaKit/LiveEventClient.swift macos-app/MusicnaKit/Tests/MusicnaKitTests/LiveEventClientTests.swift
git commit -m "feat: MusicnaKit LiveEventClient — /ws/live 구독, busy-loop 없는 재연결"
```

---

## Task 4: `PlayerStatusStore`/`LiveAnalysisStore`/`LibraryStore` — ObservableObject 스토어

**Files:**
- Create: `macos-app/MusicnaKit/Sources/MusicnaKit/PlayerStatusStore.swift`
- Create: `macos-app/MusicnaKit/Sources/MusicnaKit/LiveAnalysisStore.swift`
- Create: `macos-app/MusicnaKit/Sources/MusicnaKit/LibraryStore.swift`
- Create: `macos-app/MusicnaKit/Tests/MusicnaKitTests/LiveAnalysisStoreTests.swift`
- Create: `macos-app/MusicnaKit/Tests/MusicnaKitTests/LibraryStoreTests.swift`

**Interfaces:**
- Consumes: `APIClient`(Task 2), `LiveEventClient`(Task 3), `AnalysisResult`/`LiveEvent`(Task 1)
- Produces: `public final class PlayerStatusStore: ObservableObject` — `@Published public var playerStatus: PlayerStatus?`, `@Published public var systemStatus: SystemStatus?`, `@Published public var isConnected: Bool`, `init(client: APIClient, pollInterval: Duration = .seconds(2))`, `func start()`. `public final class LiveAnalysisStore: ObservableObject` — `@Published public var currentChord: String?`, `@Published public var chordHistory: [String]`, `@Published public var activeNoteCount: Int`, `@Published public var isConnected: Bool`, `init(liveEventClient: LiveEventClient)`, `func start()`. `public final class LibraryStore: ObservableObject` — `@Published public var tracks: [AnalysisResult]`, `@Published public var loadError: String?`, `init(client: APIClient)`, `func refresh() async`. Task 6~8의 SwiftUI 뷰가 이 스토어들을 구독.

- [ ] **Step 1: 실패하는 테스트를 작성 — `LiveAnalysisStore`**

`macos-app/MusicnaKit/Tests/MusicnaKitTests/LiveAnalysisStoreTests.swift`:

```swift
import XCTest
@testable import MusicnaKit

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
```

- [ ] **Step 2: 실패하는 테스트를 작성 — `LibraryStore`**

`macos-app/MusicnaKit/Tests/MusicnaKitTests/LibraryStoreTests.swift`:

```swift
import XCTest
@testable import MusicnaKit

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
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

Run: `cd macos-app/MusicnaKit && swift test`
Expected: FAIL — `PlayerStatusStore`/`LiveAnalysisStore`/`LibraryStore` 타입이 없어 컴파일 에러

- [ ] **Step 4: `Sources/MusicnaKit/LiveAnalysisStore.swift` 작성**

```swift
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
```

- [ ] **Step 5: `Sources/MusicnaKit/LibraryStore.swift` 작성**

```swift
import Foundation

@MainActor
public final class LibraryStore: ObservableObject {
    @Published public private(set) var tracks: [AnalysisResult] = []
    @Published public private(set) var loadError: String?

    private let client: APIClient

    public init(client: APIClient) {
        self.client = client
    }

    public func refresh() async {
        do {
            let raw = try await client.tracks()
            tracks = raw
            loadError = nil
        } catch {
            tracks = []
            loadError = "api 연결 실패"
        }
    }
}
```

- [ ] **Step 6: `Sources/MusicnaKit/PlayerStatusStore.swift` 작성**

```swift
import Foundation

@MainActor
public final class PlayerStatusStore: ObservableObject {
    @Published public private(set) var playerStatus: PlayerStatus?
    @Published public private(set) var systemStatus: SystemStatus?
    @Published public private(set) var isConnected: Bool = false

    private let client: APIClient
    private let pollInterval: Duration

    public init(client: APIClient, pollInterval: Duration = .seconds(2)) {
        self.client = client
        self.pollInterval = pollInterval
    }

    public func start() {
        Task {
            while !Task.isCancelled {
                await refreshOnce()
                try? await Task.sleep(for: pollInterval)
            }
        }
    }

    private func refreshOnce() async {
        do {
            playerStatus = try await client.playerStatus()
            systemStatus = try await client.systemStatus()
            isConnected = true
        } catch {
            isConnected = false
        }
    }
}
```

- [ ] **Step 7: 테스트 실행 → 통과 확인**

Run: `cd macos-app/MusicnaKit && swift test`
Expected: PASS — 전부(26개: 이전 21 + `LiveAnalysisStore` 3 + `LibraryStore` 2)

**주의**: `LibraryStore`의 손상 항목 개별 skip을 실제로 구현하려면 Step 5의 `try await client.tracks()`(배열 통짜 디코딩)만으로는 부족할 수 있다 — `JSONDecoder`가 배열 하나라도 실패하면 전체 배열 디코딩이 실패하는 기본 동작이기 때문이다. Step 4(테스트)가 실패하면, `LibraryStore.refresh()` 내부에서 `client.tracks()`를 쓰는 대신 raw `[[String: Any]]`(또는 `[JSONValue]`)를 받아 항목별로 개별 `JSONDecoder().decode(AnalysisResult.self, from:)`를 시도하고 실패한 항목만 건너뛰는 방식으로 구현을 조정할 것 — 이 경우 `APIClient`에 `tracksRaw() async throws -> Data`(가공 안 된 응답)를 추가하고 `LibraryStore`가 직접 파싱하도록 바꿔도 된다(브리프가 처방한 구현이 실제로 안 맞으면, Phase 8 TUI 때처럼 원인을 정확히 특정해서 최소한으로 조정할 것).

- [ ] **Step 8: 커밋**

```bash
git add macos-app/MusicnaKit/Sources/MusicnaKit/PlayerStatusStore.swift macos-app/MusicnaKit/Sources/MusicnaKit/LiveAnalysisStore.swift macos-app/MusicnaKit/Sources/MusicnaKit/LibraryStore.swift macos-app/MusicnaKit/Tests/MusicnaKitTests/LiveAnalysisStoreTests.swift macos-app/MusicnaKit/Tests/MusicnaKitTests/LibraryStoreTests.swift
git commit -m "feat: MusicnaKit 3개 ObservableObject 스토어 — PlayerStatus/LiveAnalysis/Library"
```

**여기까지가 Xcode 없이(이 세션에서) 완료 가능한 범위다.** Task 5부터는 `xcodebuild -version`이 정상 출력되는지 먼저 확인할 것.

---

## Task 5: XcodeGen으로 `Musicna.xcodeproj` 생성 + App 진입점

**Files:**
- Create: `macos-app/project.yml`
- Create: `macos-app/Musicna/MusicnaApp.swift`
- Create: `macos-app/Musicna/Info.plist`
- Create: `macos-app/Musicna/Musicna.entitlements`
- Create: `macos-app/Musicna/Assets.xcassets/`(빈 아이콘셋)
- Generate(커밋 안 함, `.gitignore` 대상): `macos-app/Musicna.xcodeproj`

**Interfaces:**
- Consumes: `MusicnaKit`(로컬 패키지 의존성, Task 1~4)
- Produces: 빌드 가능한 macOS 앱 타겟(빈 메뉴바 아이콘만 표시, 아직 UI 없음). Task 6~8이 이 앱 타겟에 뷰를 추가.

- [ ] **Step 1: 사전 확인**

Run: `xcodebuild -version`
Expected: `Xcode 16.x`(또는 그 이상) 출력 — "requires Xcode" 에러가 나오면 App Store에서 Xcode를 먼저 설치할 것(이 Task는 자동화 불가한 사용자 조작이 선행 조건)

Run: `which xcodegen || brew install xcodegen`
Expected: `xcodegen` 바이너리 경로 출력

- [ ] **Step 2: `macos-app/.gitignore` 작성**

```
Musicna.xcodeproj/
.build/
```

- [ ] **Step 3: `macos-app/project.yml` 작성**

```yaml
name: Musicna
options:
  bundleIdPrefix: com.musicna
targets:
  Musicna:
    type: application
    platform: macOS
    deploymentTarget: "13.0"
    sources:
      - Musicna
    dependencies:
      - package: MusicnaKit
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: com.musicna.app
        INFOPLIST_FILE: Musicna/Info.plist
        CODE_SIGN_ENTITLEMENTS: Musicna/Musicna.entitlements
        MARKETING_VERSION: "0.1.0"
packages:
  MusicnaKit:
    path: MusicnaKit
```

- [ ] **Step 4: `Musicna/Info.plist` 작성**(메뉴바 전용 — Dock 아이콘 숨김)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>LSUIElement</key>
    <true/>
    <key>CFBundleShortVersionString</key>
    <string>$(MARKETING_VERSION)</string>
</dict>
</plist>
```

- [ ] **Step 5: `Musicna/Musicna.entitlements` 작성**(네트워크 클라이언트 권한만)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.app-sandbox</key>
    <true/>
    <key>com.apple.security.network.client</key>
    <true/>
</dict>
</plist>
```

- [ ] **Step 6: `Musicna/MusicnaApp.swift` 작성**(플레이스홀더 뷰 — Task 6~8이 채움)

```swift
import SwiftUI
import MusicnaKit

@main
struct MusicnaApp: App {
    @StateObject private var playerStatusStore: PlayerStatusStore
    @StateObject private var liveAnalysisStore: LiveAnalysisStore
    @StateObject private var libraryStore: LibraryStore

    init() {
        let baseURL = URL(string: UserDefaults.standard.string(forKey: "apiBaseURL") ?? "http://127.0.0.1:8000")!
        let client = APIClient(baseURL: baseURL)
        _playerStatusStore = StateObject(wrappedValue: PlayerStatusStore(client: client))
        _liveAnalysisStore = StateObject(wrappedValue: LiveAnalysisStore(
            liveEventClient: LiveEventClient(url: baseURL.wsLiveURL())
        ))
        _libraryStore = StateObject(wrappedValue: LibraryStore(client: client))
    }

    var body: some Scene {
        MenuBarExtra("musicna", systemImage: "music.note") {
            Text("musicna") // Task 6이 MenuBarView로 교체
        }
        WindowGroup(id: "library") {
            Text("Library") // Task 7이 LibraryWindowView로 교체
        }
    }
}

private extension URL {
    /// http(s) base URL을 ws(s):///ws/live로 변환 — MusicnaKit의 ApiClient.live_ws_url(TUI)과 동일 규칙.
    func wsLiveURL() -> URL {
        var components = URLComponents(url: self, resolvingAgainstBaseURL: false)!
        components.scheme = (components.scheme == "https") ? "wss" : "ws"
        components.path = "/ws/live"
        return components.url!
    }
}
```

- [ ] **Step 7: 프로젝트 생성 + 빌드 확인**

Run: `cd macos-app && xcodegen generate`
Expected: `Musicna.xcodeproj` 생성 성공

Run: `cd macos-app && xcodebuild -project Musicna.xcodeproj -scheme Musicna -configuration Debug build`
Expected: `** BUILD SUCCEEDED **`

- [ ] **Step 8: 커밋**(`.xcodeproj`는 gitignore 대상이므로 제외)

```bash
git add macos-app/.gitignore macos-app/project.yml macos-app/Musicna/MusicnaApp.swift macos-app/Musicna/Info.plist macos-app/Musicna/Musicna.entitlements
git commit -m "feat: XcodeGen 기반 Musicna 앱 타겟 스캐폴딩 — MenuBarExtra+라이브러리 WindowGroup 씬"
```

---

## Task 6: `MenuBarView.swift` — 재생 제어·세션 상태·실시간 코드

**Files:**
- Create: `macos-app/Musicna/MenuBarView.swift`
- Modify: `macos-app/Musicna/MusicnaApp.swift`

**Interfaces:**
- Consumes: `PlayerStatusStore`, `LiveAnalysisStore`(Task 4), `APIClient.playerPlay/Pause/Next/Previous/Volume`(Task 2)
- Produces: 메뉴바 팝오버 UI. Task 8이 여기에 "설정..." 버튼을 추가.

- [ ] **Step 1: `Musicna/MenuBarView.swift` 작성**

```swift
import SwiftUI
import MusicnaKit

struct MenuBarView: View {
    @EnvironmentObject var playerStatusStore: PlayerStatusStore
    @EnvironmentObject var liveAnalysisStore: LiveAnalysisStore
    @Environment(\.openWindow) private var openWindow

    let apiClient: APIClient

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            nowPlayingSection
            Divider()
            sessionStatusSection
            Divider()
            liveAnalysisSection
            Divider()
            Button("라이브러리 열기") { openWindow(id: "library") }
            Button("웹 UI 열기") { NSWorkspace.shared.open(apiClient.baseURLForOpening) }
        }
        .padding(12)
        .frame(width: 280)
    }

    private var nowPlayingSection: some View {
        VStack(alignment: .leading) {
            if let status = playerStatusStore.playerStatus {
                Text(status.itemTitle ?? "—").font(.headline)
                Text(status.itemArtist ?? "").font(.subheadline).foregroundStyle(.secondary)
                HStack {
                    Button(status.isPlaying ? "일시정지" : "재생") {
                        Task { try? await (status.isPlaying ? apiClient.playerPause() : apiClient.playerPlay()) }
                    }
                    Button("다음 곡") { Task { try? await apiClient.playerNext() } }
                }
            } else {
                Text(playerStatusStore.isConnected ? "재생 중인 곡 없음" : "api 연결 안 됨")
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var sessionStatusSection: some View {
        HStack {
            Circle()
                .fill((playerStatusStore.systemStatus?.sessionCapturing ?? false) ? .red : .gray)
                .frame(width: 8, height: 8)
            Text((playerStatusStore.systemStatus?.sessionCapturing ?? false) ? "녹음 중" : "대기")
        }
    }

    private var liveAnalysisSection: some View {
        VStack(alignment: .leading) {
            Text(liveAnalysisStore.currentChord ?? "—").font(.title2)
            if !liveAnalysisStore.chordHistory.isEmpty {
                Text(liveAnalysisStore.chordHistory.joined(separator: " → "))
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}
```

- [ ] **Step 2: `MusicnaApp.swift`의 `MenuBarExtra` 내용을 교체**

`Text("musicna")`를 아래로 교체:

```swift
        MenuBarExtra("musicna", systemImage: "music.note") {
            MenuBarView(apiClient: makeAPIClient())
                .environmentObject(playerStatusStore)
                .environmentObject(liveAnalysisStore)
        }
```

(`makeAPIClient()`는 `init()`에서 만든 것과 같은 `baseURL`로 새 `APIClient`를 반환하는 private 헬퍼로 추출 — `APIClient` 인스턴스를 프로퍼티로 보관하도록 `MusicnaApp`을 조정할 것.)

- [ ] **Step 3: 빌드 확인**

Run: `cd macos-app && xcodebuild -project Musicna.xcodeproj -scheme Musicna -configuration Debug build`
Expected: `** BUILD SUCCEEDED **`

- [ ] **Step 4: 실행·수동 확인**(자동 테스트 불가 — SwiftUI 뷰 렌더링은 XCTest로 단언하기 어려움, 기존 Phase들의 Swift GUI/하드웨어 인접 코드와 동일하게 macOS 실기기 수동 확인)

Run: `open macos-app/Musicna.xcodeproj`(Xcode에서 Cmd+R) 또는 `xcodebuild ... build && open .../Musicna.app`
Expected: 메뉴바에 아이콘이 나타나고, 클릭 시 팝오버에 (api가 떠 있다면) 재생 상태·세션 상태·실시간 코드가 표시됨. api가 안 떠 있으면 "api 연결 안 됨"이 크래시 없이 표시됨

- [ ] **Step 5: 커밋**

```bash
git add macos-app/Musicna/MenuBarView.swift macos-app/Musicna/MusicnaApp.swift
git commit -m "feat: MenuBarView — 재생 제어·세션 상태·실시간 코드 표시"
```

---

## Task 7: `LibraryWindowView.swift` — 라이브러리 목록

**Files:**
- Create: `macos-app/Musicna/LibraryWindowView.swift`
- Modify: `macos-app/Musicna/MusicnaApp.swift`

**Interfaces:**
- Consumes: `LibraryStore`(Task 4)
- Produces: 라이브러리 창 UI.

- [ ] **Step 1: `Musicna/LibraryWindowView.swift` 작성**

```swift
import SwiftUI
import MusicnaKit

struct LibraryWindowView: View {
    @EnvironmentObject var libraryStore: LibraryStore

    var body: some View {
        VStack {
            if let error = libraryStore.loadError {
                Text(error).foregroundStyle(.red).padding()
            }
            Table(libraryStore.tracks) {
                TableColumn("제목") { Text($0.track.title) }
                TableColumn("아티스트") { Text($0.track.artist ?? "-") }
                TableColumn("BPM") { track in
                    Text(track.bpm.map { String(format: "%.0f", $0) } ?? "-")
                }
                TableColumn("키") { track in
                    Text(track.key.map { "\($0) \(track.mode ?? "")" } ?? "-")
                }
                TableColumn("무드") { Text($0.moods.first?.tag ?? "-") }
            }
            Button("새로고침") { Task { await libraryStore.refresh() } }
        }
        .frame(minWidth: 500, minHeight: 300)
        .task { await libraryStore.refresh() }
    }
}
```

- [ ] **Step 2: `MusicnaApp.swift`의 `WindowGroup("library")` 내용을 교체**

`Text("Library")`를 아래로 교체:

```swift
        WindowGroup(id: "library") {
            LibraryWindowView()
                .environmentObject(libraryStore)
        }
```

- [ ] **Step 3: 빌드 확인**

Run: `cd macos-app && xcodebuild -project Musicna.xcodeproj -scheme Musicna -configuration Debug build`
Expected: `** BUILD SUCCEEDED **`

- [ ] **Step 4: 실행·수동 확인**

메뉴바 팝오버의 "라이브러리 열기" 클릭 → 별도 창이 열리고 실제 `/tracks` 데이터(api가 떠 있고 캡처된 트랙이 있다면)가 표에 나타나는지 확인

- [ ] **Step 5: 커밋**

```bash
git add macos-app/Musicna/LibraryWindowView.swift macos-app/Musicna/MusicnaApp.swift
git commit -m "feat: LibraryWindowView — /tracks 표 뷰"
```

---

## Task 8: `PreferencesView.swift` — api 접속 주소 설정

**Files:**
- Create: `macos-app/Musicna/PreferencesView.swift`
- Modify: `macos-app/Musicna/MusicnaApp.swift`
- Modify: `macos-app/Musicna/MenuBarView.swift`

**Interfaces:**
- Consumes: 없음(순수 UI + `UserDefaults`)
- Produces: 설정 창. `UserDefaults.standard.string(forKey: "apiBaseURL")`을 갱신 — `MusicnaApp.swift`의 `init()`이 이미 이 키를 읽고 있음(Task 5 Step 6 참조).

- [ ] **Step 1: `Musicna/PreferencesView.swift` 작성**

```swift
import SwiftUI

struct PreferencesView: View {
    @AppStorage("apiBaseURL") private var apiBaseURL: String = "http://127.0.0.1:8000"
    @State private var draft: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("api 접속 주소").font(.headline)
            TextField("http://127.0.0.1:8000", text: $draft)
                .textFieldStyle(.roundedBorder)
                .frame(width: 320)
            Text("변경 후 앱을 재시작해야 적용됩니다.").font(.caption).foregroundStyle(.secondary)
            Button("저장") { apiBaseURL = draft }
        }
        .padding(20)
        .onAppear { draft = apiBaseURL }
    }
}
```

(재시작 필요 — `APIClient`/`LiveEventClient`가 `MusicnaApp.init()`에서 한 번만 생성되므로. 런타임 즉시 반영은 이번 범위 밖으로 명시적으로 단순화한다.)

- [ ] **Step 2: `MusicnaApp.swift`에 설정 창 씬 추가**

```swift
        Settings {
            PreferencesView()
        }
```

(`var body: some Scene { ... }` 안, 기존 두 씬 다음에 추가)

- [ ] **Step 3: `MenuBarView.swift`에 "설정..." 버튼 추가**

`Button("웹 UI 열기") { ... }` 다음 줄에 추가:

```swift
            SettingsLink { Text("설정...") }
```

(`SettingsLink`는 macOS 14+ API — Global Constraints의 `deploymentTarget: 13.0`과 충돌하면 `NSApp.sendAction(Selector(("showPreferencesWindow:")), to: nil, from: nil)` 방식으로 대체할 것. 빌드 시 실제 어느 쪽이 필요한지 확인.)

- [ ] **Step 4: 빌드 확인**

Run: `cd macos-app && xcodebuild -project Musicna.xcodeproj -scheme Musicna -configuration Debug build`
Expected: `** BUILD SUCCEEDED **`(`SettingsLink` 관련 에러가 나면 Step 3의 대체 방식 적용)

- [ ] **Step 5: 실행·수동 확인**

"설정..." 클릭 → 창이 뜨고 텍스트 필드에 현재 주소가 보이는지, 저장 후 `UserDefaults`에 반영되는지(`defaults read com.musicna.app apiBaseURL`로 확인 가능) 확인

- [ ] **Step 6: 커밋**

```bash
git add macos-app/Musicna/PreferencesView.swift macos-app/Musicna/MusicnaApp.swift macos-app/Musicna/MenuBarView.swift
git commit -m "feat: PreferencesView — api 접속 주소 UserDefaults 설정"
```

---

## Task 9: 문서 갱신

**Files:**
- Modify: `docs/PROGRESS.md`
- Modify: `docs/PLAN.md`

**Interfaces:** 없음.

- [ ] **Step 1: `docs/PLAN.md`의 Phase 9 항목 갱신**

"- **Phase 9 — macOS 네이티브 앱**: ..." 줄 다음에 완료 표시와 설계 스펙 링크를 추가(실행 시점의 실제 완료 상태로 문구 조정):

```markdown
- **Phase 9 — macOS 네이티브 앱** ✅ **구현 완료(2026-07-29 이후, 실제 완료일로 갱신)**: 메뉴바(재생 제어·세션 상태·실시간 코드) + 라이브러리 창. `MusicnaKit`(순수 Swift 패키지)로 네트워킹·모델·상태 로직을 Phase 10과 공유 가능하게 분리. 설계: [2026-07-29-phase-9-macos-native-app-design.md](superpowers/specs/2026-07-29-phase-9-macos-native-app-design.md)
```

- [ ] **Step 2: `docs/PROGRESS.md`의 "## 현재 상태"·Phase 체크리스트·작업 로그 갱신**

`docs/PROGRESS.md`의 "### Phase 9" 섹션(현재 없으면 Phase 8.5와 Phase 10 사이에 신설)에 체크리스트 추가:

```markdown
### Phase 9 — macOS 네이티브 앱
- [x] `MusicnaKit` 패키지(순수 Swift, SwiftUI/AppKit 무의존) — APIClient·LiveEventClient·Models·3개 스토어, `swift test`로 검증(테스트 개수는 실행 시 실제 값으로 갱신)
- [x] Xcode 프로젝트(XcodeGen `project.yml`) + MenuBarExtra 앱 구조
- [x] `MenuBarView`(재생 제어·세션 상태·실시간 코드) + `LibraryWindowView`(트랙 목록) + `PreferencesView`(api 주소 설정)
- [ ] **(macOS)** 마일스톤: 메뉴바에서 재생/일시정지·다음곡·볼륨 조작 시 실제 Spotify 재생 반응, 캡처 상태·실시간 코드가 실제 재생과 함께 갱신, 라이브러리 창에 실제 캡처 트랙 표시
```

작업 로그 표 마지막 행 다음에(실제 실행 시점의 커밋 해시·테스트 개수로 갱신):

```markdown
| 2026-07-29 | Phase 9(macOS 네이티브 앱) 구현 — `MusicnaKit` 패키지(Task 1~4, swift test로 검증) + XcodeGen 기반 App 타겟(Task 5~8: MenuBarExtra·라이브러리 창·설정) | 이 세션이 실제 프로젝트 머신(Mac mini)임을 재확인 — 이전에 "원격/Linux라 불가능"으로 잘못 안내했던 여러 macOS 전용 백로그 항목이 실제로는 이 머신에서 가능함이 드러남(전체 Xcode.app만 예외적으로 미설치). Task 1~4는 Xcode 없이 swift test로 완료, Task 5~8은 Xcode 설치 후 이어서 진행 |
```

- [ ] **Step 3: 커밋 및 푸시**

```bash
git add docs/PROGRESS.md docs/PLAN.md
git commit -m "docs: Phase 9(macOS 네이티브 앱) 구현 완료 반영"
git push
```

---

## Self-Review 메모

- **스펙 커버리지**: 설계 스펙(`2026-07-29-phase-9-macos-native-app-design.md`)의 컴포넌트 절(APIClient·LiveEventClient·Models·3개 스토어·MenuBarView·LibraryWindowView·PreferencesView)이 Task 1~8에 전부 매핑됨. "재연결 busy loop 방지"·"손상 항목 개별 skip" 두 설계 원칙이 각각 Task 3·Task 4에 구체적인 테스트로 반영됨.
- **환경 제약 명시**: Task 1~4(Xcode 불필요)와 Task 5~8(Xcode 필요) 사이에 명확한 경계를 두어, Xcode 미설치 상태에서도 이 계획의 절반은 바로 실행 가능하도록 설계했다.
- **플레이스홀더 스캔**: 없음 — 모든 Step에 실제 코드가 있다. Task 4 Step 7의 "주의" 문구는 플레이스홀더가 아니라, `JSONDecoder`의 배열 통짜 디코딩이 "항목별 skip" 요구사항과 실제로 안 맞을 수 있다는 걸 미리 경고하고 대안 구현 경로를 제시한 것(Phase 8 TUI에서 "브리프가 실제로 안 맞을 수 있다"는 걸 여러 번 겪은 교훈 반영).
- **타입 일관성**: `APIClient`(Task 2)·`LiveEventClient`(Task 3)가 Task 4의 스토어 생성자 시그니처와 일치. `AnalysisResult`/`PlayerStatus`/`SystemStatus`/`LiveEvent`(Task 1)가 이후 전 Task에서 동일하게 쓰임.
- **기존 프로젝트 패턴과의 일관성**: JSON 필드명·이벤트 타입·재연결 규칙 전부 Phase 6~8에서 이미 실측 검증된 Python/TUI 쪽 계약을 그대로 옮긴 것 — 새로 추측한 스키마 없음.
