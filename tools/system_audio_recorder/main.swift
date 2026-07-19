import AVFAudio
import CoreMedia
import Foundation
import ScreenCaptureKit

@available(macOS 13.0, *)
extension CMSampleBuffer {
    func toPCMBuffer() -> AVAudioPCMBuffer? {
        guard let formatDescription = CMSampleBufferGetFormatDescription(self),
            let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(formatDescription)
        else {
            return nil
        }
        guard let format = AVAudioFormat(streamDescription: asbd) else { return nil }

        var bufferListSizeNeeded = 0
        var status = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
            self,
            bufferListSizeNeededOut: &bufferListSizeNeeded,
            bufferListOut: nil,
            bufferListSize: 0,
            blockBufferAllocator: kCFAllocatorDefault,
            blockBufferMemoryAllocator: kCFAllocatorDefault,
            flags: kCMSampleBufferFlag_AudioBufferList_Assure16ByteAlignment,
            blockBufferOut: nil
        )
        guard status == noErr, bufferListSizeNeeded > 0 else { return nil }

        let rawListPointer = UnsafeMutableRawPointer.allocate(
            byteCount: bufferListSizeNeeded,
            alignment: MemoryLayout<AudioBufferList>.alignment
        )
        defer { rawListPointer.deallocate() }
        let listPointer = rawListPointer.bindMemory(to: AudioBufferList.self, capacity: 1)

        var blockBuffer: CMBlockBuffer?
        status = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
            self,
            bufferListSizeNeededOut: nil,
            bufferListOut: listPointer,
            bufferListSize: bufferListSizeNeeded,
            blockBufferAllocator: kCFAllocatorDefault,
            blockBufferMemoryAllocator: kCFAllocatorDefault,
            flags: kCMSampleBufferFlag_AudioBufferList_Assure16ByteAlignment,
            blockBufferOut: &blockBuffer
        )
        guard status == noErr else { return nil }

        let frameCount = CMSampleBufferGetNumSamples(self)
        guard
            let pcmBuffer = AVAudioPCMBuffer(
                pcmFormat: format,
                bufferListNoCopy: listPointer,
                deallocator: { _ in blockBuffer = nil }
            )
        else {
            return nil
        }
        pcmBuffer.frameLength = AVAudioFrameCount(frameCount)
        return pcmBuffer
    }
}

@available(macOS 13.0, *)
final class SystemAudioRecorder: NSObject, SCStreamOutput, SCStreamDelegate {
    private let outputURL: URL
    private let queue = DispatchQueue(label: "system-audio-recorder.output")
    private var stream: SCStream?
    private var audioFile: AVAudioFile?

    init(outputURL: URL) {
        self.outputURL = outputURL
    }

    func start() async throws {
        let content = try await SCShareableContent.excludingDesktopWindows(
            false,
            onScreenWindowsOnly: false
        )
        guard let display = content.displays.first else {
            throw NSError(
                domain: "SystemAudioRecorder",
                code: 1,
                userInfo: [NSLocalizedDescriptionKey: "No display found to attach an audio-only capture to"]
            )
        }

        let filter = SCContentFilter(display: display, excludingWindows: [])
        let config = SCStreamConfiguration()
        config.capturesAudio = true
        config.sampleRate = 48000
        config.channelCount = 2
        config.width = 2
        config.height = 2
        config.minimumFrameInterval = CMTime(value: 1, timescale: 1)
        config.showsCursor = false

        let stream = SCStream(filter: filter, configuration: config, delegate: self)
        try stream.addStreamOutput(self, type: .audio, sampleHandlerQueue: queue)
        self.stream = stream
        try await stream.startCapture()
    }

    func stop() async {
        try? await stream?.stopCapture()
        stream = nil
        queue.sync {
            audioFile = nil
        }
    }

    func stream(
        _ stream: SCStream,
        didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
        of outputType: SCStreamOutputType
    ) {
        guard outputType == .audio, sampleBuffer.isValid else { return }
        guard let pcmBuffer = sampleBuffer.toPCMBuffer() else { return }

        if audioFile == nil {
            audioFile = try? AVAudioFile(
                forWriting: outputURL,
                settings: pcmBuffer.format.settings
            )
        }
        try? audioFile?.write(from: pcmBuffer)
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        FileHandle.standardError.write("system-audio-recorder: stream stopped with error: \(error)\n".data(using: .utf8)!)
    }
}

guard CommandLine.arguments.count > 1 else {
    FileHandle.standardError.write("Usage: system_audio_recorder <output.wav>\n".data(using: .utf8)!)
    exit(1)
}

let outputURL = URL(fileURLWithPath: CommandLine.arguments[1])

guard #available(macOS 13.0, *) else {
    FileHandle.standardError.write("system-audio-recorder requires macOS 13.0 or later\n".data(using: .utf8)!)
    exit(1)
}

let recorder = SystemAudioRecorder(outputURL: outputURL)

signal(SIGINT, SIG_IGN)
signal(SIGTERM, SIG_IGN)

let sigintSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
let sigtermSource = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)

func shutdown() {
    Task {
        await recorder.stop()
        print("STOPPED")
        exit(0)
    }
}

sigintSource.setEventHandler(handler: shutdown)
sigtermSource.setEventHandler(handler: shutdown)
sigintSource.resume()
sigtermSource.resume()

Task {
    do {
        try await recorder.start()
        print("RECORDING")
    } catch {
        FileHandle.standardError.write("system-audio-recorder: failed to start: \(error)\n".data(using: .utf8)!)
        exit(1)
    }
}

RunLoop.main.run()
