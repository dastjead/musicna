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
