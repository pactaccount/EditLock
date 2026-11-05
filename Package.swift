// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "EditLockMac",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "EditLockMac", targets: ["EditLockMac"])],
    targets: [.executableTarget(name: "EditLockMac", path: "Sources/EditLockMac")]
)
