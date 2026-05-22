// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "OpenDispatch",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "OpenDispatch",
            path: "Sources/OpenDispatch",
            resources: [
                .process("Resources"),
            ]
        ),
    ]
)
