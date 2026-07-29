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
            tracks = Self.parseTolerantly(data)
            loadError = nil
        } catch {
            tracks = []
            loadError = "api 연결 실패"
        }
    }

    /// `[AnalysisResult].self`로 배열을 통짜 디코딩하면 원소 하나만 손상돼도 전체가 실패한다
    /// (`JSONDecoder`의 기본 동작). `/tracks` 응답은 여러 세션이 축적한 결과라 개별 레코드가
    /// 손상돼 있을 수 있으므로, 최상위 JSON 배열을 직접 순회하며 원소별로 개별
    /// `JSONDecoder`를 시도하고 실패한 항목만 건너뛴다.
    private static func parseTolerantly(_ data: Data) -> [AnalysisResult] {
        guard let elements = try? JSONSerialization.jsonObject(with: data) as? [Any] else {
            return []
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
