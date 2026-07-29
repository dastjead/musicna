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
