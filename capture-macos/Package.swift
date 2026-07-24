// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "musicna-capture",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(name: "musicna-capture", path: "Sources/musicna-capture")
    ]
)
