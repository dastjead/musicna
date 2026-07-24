// musicna-capture — 시스템 오디오를 ScreenCaptureKit으로 캡처해
// 48kHz float32 interleaved stereo PCM을 stdout으로 파이프하는 CLI.
//
// 역할은 이것뿐이다. 트랙 분할·저장·메타데이터는 Python 세션 매니저(api 측) 담당.
//
// 사용:
//   musicna-capture [--app <bundle-id>]
// 로그는 stderr, PCM 바이트는 stdout. 화면 기록 권한 필요 (최초 실행 시 프롬프트).

import CoreMedia
import Foundation
import ScreenCaptureKit

let sampleRate = 48000
let channelCount = 2

func logErr(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}

/// PCM을 stdout에 쓴다. 파이프가 닫히면(EPIPE) 조용히 종료.
func writePCM(_ data: Data) {
    data.withUnsafeBytes { (buf: UnsafeRawBufferPointer) in
        guard let base = buf.baseAddress, !buf.isEmpty else { return }
        let written = fwrite(base, 1, buf.count, stdout)
        if written < buf.count {
            logErr("musicna-capture: stdout closed, exiting")
            exit(0)
        }
    }
    fflush(stdout)
}

final class AudioStreamOutput: NSObject, SCStreamOutput, SCStreamDelegate {
    func stream(
        _ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
        of type: SCStreamOutputType
    ) {
        guard type == .audio, sampleBuffer.isValid else { return }
        let frameCount = CMSampleBufferGetNumSamples(sampleBuffer)
        guard frameCount > 0 else { return }

        try? sampleBuffer.withAudioBufferList { audioBufferList, _ in
            let buffers = Array(audioBufferList)
            if buffers.count == 1, let data = buffers[0].mData {
                // 이미 인터리브된 단일 버퍼
                writePCM(Data(bytes: data, count: Int(buffers[0].mDataByteSize)))
                return
            }
            // 채널별(non-interleaved) 버퍼 → 인터리브
            var out = [Float32](repeating: 0, count: frameCount * buffers.count)
            for (ch, buf) in buffers.enumerated() {
                guard let data = buf.mData else { continue }
                let src = data.assumingMemoryBound(to: Float32.self)
                for i in 0..<frameCount {
                    out[i * buffers.count + ch] = src[i]
                }
            }
            out.withUnsafeBytes { writePCM(Data($0)) }
        }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        logErr("musicna-capture: stream stopped: \(error.localizedDescription)")
        exit(1)
    }
}

func parseAppArg() -> String? {
    let args = CommandLine.arguments
    guard let i = args.firstIndex(of: "--app"), i + 1 < args.count else { return nil }
    return args[i + 1]
}

@main
struct Main {
    static func main() async {
        signal(SIGPIPE, SIG_IGN)

        do {
            let content = try await SCShareableContent.excludingDesktopWindows(
                false, onScreenWindowsOnly: false)
            guard let display = content.displays.first else {
                logErr("musicna-capture: no display found")
                exit(1)
            }

            let filter: SCContentFilter
            if let bundleID = parseAppArg() {
                guard let app = content.applications.first(where: { $0.bundleIdentifier == bundleID })
                else {
                    logErr("musicna-capture: app not running: \(bundleID)")
                    exit(1)
                }
                filter = SCContentFilter(
                    display: display, including: [app], exceptingWindows: [])
                logErr("musicna-capture: capturing audio of \(bundleID)")
            } else {
                filter = SCContentFilter(display: display, excludingWindows: [])
                logErr("musicna-capture: capturing system audio")
            }

            let config = SCStreamConfiguration()
            config.capturesAudio = true
            config.excludesCurrentProcessAudio = true
            config.sampleRate = sampleRate
            config.channelCount = channelCount
            // 비디오는 필요 없지만 스트림 구성상 최소값으로 유지
            config.width = 2
            config.height = 2
            config.minimumFrameInterval = CMTime(value: 1, timescale: 1)

            let output = AudioStreamOutput()
            let stream = SCStream(filter: filter, configuration: config, delegate: output)
            try stream.addStreamOutput(
                output, type: .audio,
                sampleHandlerQueue: DispatchQueue(label: "musicna.capture.audio"))
            try await stream.startCapture()
            logErr("musicna-capture: started (\(sampleRate)Hz float32 x\(channelCount)ch → stdout)")

            // SIGINT/SIGTERM까지 대기
            signal(SIGINT, SIG_IGN)
            signal(SIGTERM, SIG_IGN)
            let stopped = AsyncStream<Void> { continuation in
                for sig in [SIGINT, SIGTERM] {
                    let src = DispatchSource.makeSignalSource(signal: sig, queue: .global())
                    src.setEventHandler { continuation.yield() }
                    src.resume()
                    _ = Unmanaged.passRetained(src)  // 프로세스 종료까지 유지
                }
            }
            for await _ in stopped { break }

            logErr("musicna-capture: stopping")
            try? await stream.stopCapture()
            exit(0)
        } catch {
            logErr("musicna-capture: error: \(error.localizedDescription)")
            exit(1)
        }
    }
}
