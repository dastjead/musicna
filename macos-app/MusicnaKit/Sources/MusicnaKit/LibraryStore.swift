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
            let data = try await client.tracksRaw()
            tracks = try Self.parseTolerantly(data)
            loadError = nil
        } catch {
            tracks = []
            loadError = "api 연결 실패"
        }
    }

    /// 최상위 구조 파싱 실패(끊긴 바디, 배열이 아닌 JSON, 비-JSON 텍스트 등)를 나타낸다.
    /// 원소 단위 관용 처리("손상 항목 개별 skip")와는 별개 실패 모드 — 최상위 자체가
    /// 배열이 아니면 "정상적으로 빈 라이브러리"가 아니라 명백한 에러이므로, `refresh()`가
    /// 이를 network 실패와 동일하게 `loadError`로 표면화할 수 있도록 던진다.
    private struct MalformedTopLevelResponse: Error {}

    /// `[AnalysisResult].self`로 배열을 통짜 디코딩하면 원소 하나만 손상돼도 전체가 실패한다
    /// (`JSONDecoder`의 기본 동작). `/tracks` 응답은 여러 세션이 축적한 결과라 개별 레코드가
    /// 손상돼 있을 수 있으므로, 최상위 JSON 배열을 직접 순회하며 원소별로 개별
    /// `JSONDecoder`를 시도하고 실패한 항목만 건너뛴다. 단, 최상위 자체가 배열이 아니면
    /// (조용히 빈 배열로 흡수하지 않고) `MalformedTopLevelResponse`를 던진다.
    private static func parseTolerantly(_ data: Data) throws -> [AnalysisResult] {
        let parsed = try JSONSerialization.jsonObject(with: data)
        guard let elements = parsed as? [Any] else {
            throw MalformedTopLevelResponse()
        }
        let decoder = JSONDecoder()
        return elements.compactMap { element in
            guard let elementData = try? JSONSerialization.data(withJSONObject: element) else {
                return nil
            }
            return try? decoder.decode(AnalysisResult.self, from: elementData)
        }
    }
}
