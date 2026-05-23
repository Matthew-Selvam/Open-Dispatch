// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "OpenDispatch",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "OpenDispatch",
            path: "Sources/OpenDispatch",
            // Info.plist is copied into the .app bundle directly by
            // scripts/make-dmg.sh. SwiftPM forbids a top-level Info.plist as a
            // bundled resource, so exclude it from the target instead of
            // .process("Resources") (which would sweep it in and fail the build).
            exclude: ["Resources/Info.plist"]
        ),
    ]
)
