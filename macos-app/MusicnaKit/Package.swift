// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "MusicnaKit",
    platforms: [.macOS(.v13), .iOS(.v16)],
    products: [
        .library(name: "MusicnaKit", targets: ["MusicnaKit"]),
    ],
    targets: [
        .target(name: "MusicnaKit"),
        .testTarget(name: "MusicnaKitTests", dependencies: ["MusicnaKit"]),
    ]
)
