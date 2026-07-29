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
        let json = """
        {"type": "note_off", "index": 1, "end_s": 1.5}
        """.data(using: .utf8)!
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
        let json = """
        {"type": "track_ended"}
        """.data(using: .utf8)!
        let event = try JSONDecoder().decode(LiveEvent.self, from: json)
        XCTAssertEqual(event, .trackEnded)
    }

    func testLiveEventUnknownTypeThrows() {
        let json = """
        {"type": "something_new"}
        """.data(using: .utf8)!
        XCTAssertThrowsError(try JSONDecoder().decode(LiveEvent.self, from: json))
    }
}
