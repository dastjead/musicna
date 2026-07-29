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
