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
