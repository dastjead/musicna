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
