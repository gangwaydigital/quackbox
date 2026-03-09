// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "QuackBoxNative",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "QuackBoxNative", targets: ["QuackBoxNative"])
    ],
    targets: [
        .executableTarget(
            name: "QuackBoxNative",
            path: "Sources/QuackBoxNative"
        )
    ]
)
