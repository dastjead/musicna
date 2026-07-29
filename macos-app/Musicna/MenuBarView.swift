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
