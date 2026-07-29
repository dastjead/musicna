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
