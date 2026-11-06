import AppKit
import Foundation
import SwiftUI
import UniformTypeIdentifiers

// MARK: - Editing state

struct MaskStroke {
    let points: [CGPoint]  // Image pixel coordinates, origin at top left.
    let erase: Bool
    let width: CGFloat
}

struct EditVersion {
    let sourceURL: URL
    let sourceImage: NSImage
    let resultURL: URL
    let resultImage: NSImage
    let instruction: String
    let strokes: [MaskStroke]
    let lockOutsidePaint: Bool
    let seed: Int
}

enum ViewMode: String, CaseIterable, Identifiable {
    case original = "Original"
    case previous = "Previous"
    case result = "Result"

    var id: String { rawValue }
}

private struct PrepareRequest: Encodable { let image_path: String }
private struct PrepareResponse: Decodable { let image_path: String; let width: Int; let height: Int }
private struct EditRequestBody: Encodable {
    let image_path: String
    let mask_path: String?
    let mode: String
    let instruction: String
    let seed: Int
    let feather_px: Int
}
private struct EditResponse: Decodable {
    let output_path: String
    let elapsed_seconds: Double
    let mode: String
    let protected_pixels_identical: Bool?
}
private struct APIError: Decodable { let detail: String }

enum EditLockAppError: LocalizedError {
    case message(String)
    var errorDescription: String? {
        if case .message(let text) = self { return text }
        return nil
    }
}

@MainActor
final class EditLockState: ObservableObject {
    @Published var photo: NSImage?
    @Published var result: NSImage?
    @Published var maskPreview: NSImage?
    @Published var instruction = ""
    @Published var brushSize = 55.0
    @Published var maskMargin = 0.0 { didSet { rebuildMaskPreview() } }
    @Published var lockOutsidePaint = false
    @Published var erasing = false
    @Published var viewMode: ViewMode = .original
    @Published var isBusy = false
    @Published var status = "Import a photo to begin."
    @Published var errorMessage: String?
    @Published var strokes: [MaskStroke] = []

    @Published private(set) var originalPhoto: NSImage?
    @Published private(set) var originalURL: URL?
    @Published private(set) var history: [EditVersion] = []

    var displayedImage: NSImage? {
        switch viewMode {
        case .original:
            return originalPhoto ?? photo
        case .previous:
            return photo
        case .result:
            return result ?? photo
        }
    }

    var isPaintingAllowed: Bool {
        guard !isBusy, photo != nil else { return false }
        if history.isEmpty {
            return viewMode == .original
        } else {
            return viewMode == .previous
        }
    }

    var availableViewModes: [ViewMode] {
        if result != nil {
            return history.isEmpty ? [.original, .result] : [.original, .previous, .result]
        } else {
            return history.isEmpty ? [.original] : [.original, .previous]
        }
    }

    private(set) var sourceURL: URL?
    private(set) var resultURL: URL?
    private(set) var imageSize = CGSize.zero
    private var engine: Process?
    private let token = UUID().uuidString
    private let port = Int.random(in: 41000...59000)
    private var seed = 42
    private var activeTask: Task<Void, Never>?

    private var root: URL {
        if let location = ProcessInfo.processInfo.environment["EDITLOCK_ROOT"] {
            return URL(fileURLWithPath: location, isDirectory: true)
        }
        var directory = URL(fileURLWithPath: CommandLine.arguments[0])
            .resolvingSymlinksInPath().deletingLastPathComponent()
        for _ in 0..<8 {
            if FileManager.default.fileExists(
                atPath: directory.appendingPathComponent(".venv/bin/python").path
            ) { return directory }
            directory.deleteLastPathComponent()
        }
        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true)
    }

    func importPhoto(_ selectedURL: URL) {
        activeTask = Task {
            isBusy = true
            status = "Preparing photo…"
            defer { isBusy = false }
            let accessed = selectedURL.startAccessingSecurityScopedResource()
            defer { if accessed { selectedURL.stopAccessingSecurityScopedResource() } }
            do {
                try await ensureEngine()
                let prepared: PrepareResponse = try await post(
                    "prepare", PrepareRequest(image_path: selectedURL.path)
                )
                guard let image = NSImage(contentsOfFile: prepared.image_path) else {
                    throw EditLockAppError.message("The prepared photo could not be opened.")
                }
                originalPhoto = image
                originalURL = URL(fileURLWithPath: prepared.image_path)
                sourceURL = URL(fileURLWithPath: prepared.image_path)
                photo = image
                imageSize = CGSize(width: prepared.width, height: prepared.height)
                strokes = []
                history = []
                rebuildMaskPreview()
                result = nil
                resultURL = nil
                viewMode = .original
                seed = 42
                status = "Describe the change you want. Painting a focus area is optional."
            } catch {
                errorMessage = error.localizedDescription
                status = "Photo import failed."
            }
        }
    }

    func addStroke(_ stroke: MaskStroke) {
        guard photo != nil, isPaintingAllowed, !stroke.points.isEmpty else { return }
        strokes.append(stroke)
        rebuildMaskPreview()
    }

    func undoStroke() {
        guard !strokes.isEmpty else { return }
        strokes.removeLast()
        rebuildMaskPreview()
    }

    func clearMask() {
        strokes = []
        rebuildMaskPreview()
    }

    func generate() {
        guard sourceURL != nil else { errorMessage = "Import a photo first."; return }
        if lockOutsidePaint && !strokes.contains(where: { !$0.erase }) {
            errorMessage = "Paint an area before enabling outside locking."
            return
        }
        guard !instruction.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            errorMessage = "Enter an edit instruction first."
            return
        }
        activeTask = Task {
            isBusy = true
            status = "Editing on this Mac…"
            defer { isBusy = false }
            do {
                try await ensureEngine()
                let hasPaint = strokes.contains(where: { !$0.erase })
                let maskURL = hasPaint ? try writeMask() : nil
                let mode = lockOutsidePaint ? "locked" : hasPaint ? "guided" : "free"
                let request = EditRequestBody(
                    image_path: sourceURL!.path,
                    mask_path: maskURL?.path,
                    mode: mode,
                    instruction: instruction.trimmingCharacters(in: .whitespacesAndNewlines),
                    seed: seed,
                    feather_px: 10
                )
                let response: EditResponse = try await post("edit", request)
                if response.mode == "locked" && response.protected_pixels_identical != true {
                    throw EditLockAppError.message("Outside pixels changed, so this result was not accepted.")
                }
                guard let edited = NSImage(contentsOfFile: response.output_path) else {
                    throw EditLockAppError.message("The edited result could not be opened.")
                }
                resultURL = URL(fileURLWithPath: response.output_path)
                result = edited
                viewMode = .result
                seed += 1
                let detail = response.mode == "locked" ? "Outside pixels are unchanged." :
                    response.mode == "guided" ? "Painted focus was used as guidance." : "Instruction-only edit."
                status = String(format: "Edit ready in %.1f seconds. %@", response.elapsed_seconds, detail)
            } catch {
                if !Task.isCancelled {
                    errorMessage = error.localizedDescription
                    status = "Edit failed. Adjust the instruction or retry."
                }
            }
        }
    }

    func editThisResult() {
        guard let currentResult = result, let currentResultURL = resultURL,
              let currentSource = photo, let currentSourceURL = sourceURL, !isBusy else { return }
        let stepNumber = history.count + 1
        let prev = EditVersion(
            sourceURL: currentSourceURL,
            sourceImage: currentSource,
            resultURL: currentResultURL,
            resultImage: currentResult,
            instruction: instruction,
            strokes: strokes,
            lockOutsidePaint: lockOutsidePaint,
            seed: seed
        )
        history.append(prev)
        photo = currentResult
        sourceURL = currentResultURL
        result = nil
        resultURL = nil
        instruction = ""
        strokes = []
        rebuildMaskPreview()
        viewMode = .previous
        seed = 42
        status = "Editing from Step \(stepNumber) result. Enter the next instruction or paint a focus area."
    }

    func revertToPreviousVersion() {
        guard !history.isEmpty, !isBusy else { return }
        let last = history.removeLast()
        photo = last.sourceImage
        sourceURL = last.sourceURL
        instruction = last.instruction
        result = last.resultImage
        resultURL = last.resultURL
        lockOutsidePaint = last.lockOutsidePaint
        strokes = last.strokes
        rebuildMaskPreview()
        viewMode = .result
        seed = last.seed
        status = "Reverted to Step \(history.count + 1) result."
    }

    func cancel() {
        activeTask?.cancel()
        engine?.terminate()
        engine = nil
        isBusy = false
        status = "Edit cancelled. The model will reload on the next attempt."
    }

    func exportResult() {
        guard let targetURL = resultURL ?? (history.isEmpty ? nil : sourceURL) else { return }
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.png]
        panel.nameFieldStringValue = "EditLock-Result.png"
        if panel.runModal() == .OK, let destination = panel.url {
            do {
                if FileManager.default.fileExists(atPath: destination.path) {
                    try FileManager.default.removeItem(at: destination)
                }
                try FileManager.default.copyItem(at: targetURL, to: destination)
                status = "Saved to \(destination.lastPathComponent)."
            } catch { errorMessage = error.localizedDescription }
        }
    }

    func stopEngine() {
        if engine?.isRunning == true { engine?.terminate() }
        engine = nil
    }

    private func ensureEngine() async throws {
        if engine?.isRunning == true, await healthCheck() { return }
        let python = root.appendingPathComponent(".venv/bin/python")
        guard FileManager.default.fileExists(atPath: python.path) else {
            throw EditLockAppError.message("EditLock's Python environment is missing. Run the setup steps in README.md.")
        }
        let process = Process()
        process.executableURL = python
        process.arguments = ["-m", "editlock", "serve", "--port", "\(port)", "--token", token]
        process.currentDirectoryURL = root
        var environment = ProcessInfo.processInfo.environment
        environment["HF_HOME"] = root.appendingPathComponent("models/cache").path
        process.environment = environment
        let log = root.appendingPathComponent("outputs/app-service.log")
        FileManager.default.createFile(atPath: log.path, contents: nil)
        let handle = try FileHandle(forWritingTo: log)
        process.standardOutput = handle
        process.standardError = handle
        try process.run()
        engine = process
        for _ in 0..<80 {
            if await healthCheck() { return }
            if !process.isRunning { break }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        throw EditLockAppError.message("The local editing service did not start. See outputs/app-service.log.")
    }

    private func healthCheck() async -> Bool {
        guard let url = URL(string: "http://127.0.0.1:\(port)/health") else { return false }
        var request = URLRequest(url: url)
        request.setValue(token, forHTTPHeaderField: "X-EditLock-Token")
        request.timeoutInterval = 1
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch { return false }
    }

    private func post<Body: Encodable, Response: Decodable>(_ route: String, _ body: Body) async throws -> Response {
        guard let url = URL(string: "http://127.0.0.1:\(port)/\(route)") else {
            throw EditLockAppError.message("Invalid local service address.")
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(token, forHTTPHeaderField: "X-EditLock-Token")
        request.httpBody = try JSONEncoder().encode(body)
        request.timeoutInterval = 300
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw EditLockAppError.message("No response from the local editing service.")
        }
        if http.statusCode >= 400 {
            let detail = (try? JSONDecoder().decode(APIError.self, from: data).detail)
                ?? "The local edit failed (HTTP \(http.statusCode))."
            throw EditLockAppError.message(detail)
        }
        return try JSONDecoder().decode(Response.self, from: data)
    }

    private func writeMask() throws -> URL {
        guard let data = renderMaskData() else {
            throw EditLockAppError.message("Could not prepare the painted mask.")
        }
        let folder = root.appendingPathComponent("outputs/ui-masks", isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let url = folder.appendingPathComponent("\(UUID().uuidString).png")
        try data.write(to: url)
        return url
    }

    private func rebuildMaskPreview() {
        maskPreview = renderMaskData().flatMap(NSImage.init(data:))
    }

    private func renderMaskData() -> Data? {
        let width = Int(imageSize.width), height = Int(imageSize.height)
        guard width > 0, height > 0 else { return nil }
        guard let rep = NSBitmapImageRep(
            bitmapDataPlanes: nil, pixelsWide: width, pixelsHigh: height,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
            isPlanar: false, colorSpaceName: .deviceRGB,
            bytesPerRow: 0, bitsPerPixel: 0
        ), let context = NSGraphicsContext(bitmapImageRep: rep) else { return nil }
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = context
        NSColor.black.setFill()
        NSRect(x: 0, y: 0, width: width, height: height).fill()
        for stroke in strokes {
            let color = stroke.erase ? NSColor.black : NSColor.white
            color.setStroke()
            color.setFill()
            if stroke.points.count == 1, let point = stroke.points.first {
                let expandedWidth = stroke.width + CGFloat(maskMargin * 2)
                let radius = expandedWidth / 2
                NSBezierPath(ovalIn: NSRect(
                    x: point.x - radius, y: CGFloat(height) - point.y - radius,
                    width: expandedWidth, height: expandedWidth
                )).fill()
            } else if let first = stroke.points.first {
                let path = NSBezierPath()
                path.move(to: CGPoint(x: first.x, y: CGFloat(height) - first.y))
                for point in stroke.points.dropFirst() {
                    path.line(to: CGPoint(x: point.x, y: CGFloat(height) - point.y))
                }
                path.lineWidth = stroke.width + CGFloat(maskMargin * 2)
                path.lineCapStyle = .round
                path.lineJoinStyle = .round
                path.stroke()
            }
        }
        context.flushGraphics()
        NSGraphicsContext.restoreGraphicsState()
        return rep.representation(using: .png, properties: [:])
    }
}

// MARK: - Interface

struct ContentView: View {
    @EnvironmentObject private var state: EditLockState
    @State private var choosingPhoto = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("EditLock").font(.largeTitle.bold())
                    Text("Describe a change. Paint a focus area if useful.")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Import Photo") { choosingPhoto = true }
                    .disabled(state.isBusy)
            }

            HStack(alignment: .top, spacing: 18) {
                Group {
                    if let image = state.displayedImage {
                        MaskEditorView(
                            image: image,
                            mask: state.isPaintingAllowed ? state.maskPreview : nil,
                            imageSize: state.imageSize,
                            brushSize: state.brushSize,
                            erasing: state.erasing,
                            paintingEnabled: state.isPaintingAllowed,
                            onStroke: state.addStroke
                        )
                    } else {
                        ContentUnavailableView(
                            "No photo yet", systemImage: "photo.badge.plus",
                            description: Text("Import a photo to start a local edit.")
                        )
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(.quaternary.opacity(0.25), in: RoundedRectangle(cornerRadius: 16))

                controls.frame(width: 260)
            }

            HStack {
                Text(state.status).font(.callout).foregroundStyle(.secondary)
                Spacer()
                if state.isBusy { ProgressView().controlSize(.small) }
            }
        }
        .padding(20)
        .frame(minWidth: 980, minHeight: 690)
        .fileImporter(isPresented: $choosingPhoto, allowedContentTypes: [.image]) { result in
            switch result {
            case .success(let url): state.importPhoto(url)
            case .failure(let error): state.errorMessage = error.localizedDescription
            }
        }
        .alert("EditLock", isPresented: Binding(
            get: { state.errorMessage != nil },
            set: { if !$0 { state.errorMessage = nil } }
        )) {
            Button("OK") { state.errorMessage = nil }
        } message: {
            Text(state.errorMessage ?? "")
        }
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text("Optional focus area").font(.headline)
            Picker("Tool", selection: $state.erasing) {
                Text("Paint").tag(false)
                Text("Erase").tag(true)
            }
            .pickerStyle(.segmented)
            .disabled(state.photo == nil || state.isBusy)

            HStack {
                Text("Brush")
                Slider(value: $state.brushSize, in: 8...180)
                Text("\(Int(state.brushSize))").monospacedDigit().frame(width: 34)
            }
            .disabled(state.photo == nil || state.isBusy)

            HStack {
                Text("Margin")
                Slider(value: $state.maskMargin, in: 0...80)
                Text("\(Int(state.maskMargin))").monospacedDigit().frame(width: 34)
            }
            .disabled(state.photo == nil || state.isBusy)

            HStack {
                Button("Undo") { state.undoStroke() }
                Button("Clear Paint") { state.clearMask() }
            }
            .disabled(state.strokes.isEmpty || state.isBusy)

            Text("Paint guides the model. Erase removes part of the guide; other areas may still change.")
                .font(.caption).foregroundStyle(.secondary)
            Toggle("Keep outside paint unchanged", isOn: $state.lockOutsidePaint)
                .disabled(state.photo == nil || state.isBusy)
            Text("Exact outside locking needs paint and may cut off a larger edit.")
                .font(.caption).foregroundStyle(.secondary)

            Divider()
            if !state.history.isEmpty {
                HStack(spacing: 6) {
                    Text("Step \(state.history.count + 1)")
                        .font(.caption.bold())
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(.tint.opacity(0.15), in: Capsule())
                    Text("Chained edit")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            Text("Describe the edit").font(.headline)
            TextField("e.g. Change the pot to blue", text: $state.instruction, axis: .vertical)
                .lineLimit(3...5)
                .disabled(state.photo == nil || state.isBusy)
            Text("The instruction is enough to generate an edit. Painting is optional.")
                .font(.caption).foregroundStyle(.secondary)

            if state.isBusy {
                Button("Cancel Edit", role: .destructive) { state.cancel() }
            } else {
                VStack(spacing: 8) {
                    if state.result != nil {
                        Button("Edit this result") {
                            state.editThisResult()
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.accentColor)
                    }

                    if state.result == nil {
                        Button("Generate Edit") {
                            state.generate()
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(state.photo == nil || (state.lockOutsidePaint && !state.strokes.contains(where: { !$0.erase })))
                    } else {
                        Button("Retry with New Seed") {
                            state.generate()
                        }
                        .buttonStyle(.bordered)
                        .disabled(state.photo == nil || (state.lockOutsidePaint && !state.strokes.contains(where: { !$0.erase })))
                    }

                    if !state.history.isEmpty {
                        Button("Undo to Previous Version") {
                            state.revertToPreviousVersion()
                        }
                        .buttonStyle(.borderless)
                        .foregroundStyle(.secondary)
                    }
                }
            }

            Divider()
            Text("Review and export").font(.headline)
            Picker("View", selection: $state.viewMode) {
                ForEach(state.availableViewModes) { mode in
                    Text(mode.rawValue).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .disabled(state.result == nil && state.history.isEmpty)
            Button("Export PNG") { state.exportResult() }
                .disabled((state.result == nil && state.history.isEmpty) || state.isBusy)
            Spacer()
            Text("Your images and model run on this Mac.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(16)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
    }
}

private struct MaskEditorView: View {
    let image: NSImage
    let mask: NSImage?
    let imageSize: CGSize
    let brushSize: Double
    let erasing: Bool
    let paintingEnabled: Bool
    let onStroke: (MaskStroke) -> Void
    @State private var currentPoints: [CGPoint] = []

    var body: some View {
        GeometryReader { geometry in
            let rect = imageRect(in: geometry.size)
            ZStack(alignment: .topLeading) {
                Image(nsImage: image)
                    .resizable()
                    .interpolation(.high)
                    .frame(width: rect.width, height: rect.height)
                    .position(x: rect.midX, y: rect.midY)
                if let mask {
                    Color.red.opacity(0.35)
                        .frame(width: rect.width, height: rect.height)
                        .mask(
                            Image(nsImage: mask)
                                .resizable()
                                .interpolation(.none)
                                .luminanceToAlpha()
                        )
                        .position(x: rect.midX, y: rect.midY)
                }
                Canvas { context, _ in
                    guard !currentPoints.isEmpty else { return }
                    var path = Path()
                    let first = screenPoint(currentPoints[0], rect: rect)
                    path.move(to: first)
                    if currentPoints.count == 1 {
                        path.addLine(to: CGPoint(x: first.x + 0.1, y: first.y))
                    } else {
                        for point in currentPoints.dropFirst() {
                            path.addLine(to: screenPoint(point, rect: rect))
                        }
                    }
                    let scale = rect.width / imageSize.width
                    context.stroke(
                        path,
                        with: .color(erasing ? .cyan.opacity(0.7) : .red.opacity(0.7)),
                        style: StrokeStyle(lineWidth: brushSize * scale, lineCap: .round, lineJoin: .round)
                    )
                }
            }
            .frame(width: geometry.size.width, height: geometry.size.height)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0)
                .onChanged { value in
                    guard paintingEnabled, let point = imagePoint(value.location, rect: rect) else { return }
                    if let last = currentPoints.last,
                       hypot(point.x - last.x, point.y - last.y) < 2 { return }
                    currentPoints.append(point)
                }
                .onEnded { value in
                    guard paintingEnabled else { currentPoints = []; return }
                    if let point = imagePoint(value.location, rect: rect) { currentPoints.append(point) }
                    if !currentPoints.isEmpty {
                        onStroke(MaskStroke(points: currentPoints, erase: erasing, width: brushSize))
                    }
                    currentPoints = []
                }
            )
        }
    }

    private func imageRect(in available: CGSize) -> CGRect {
        guard imageSize.width > 0, imageSize.height > 0 else { return .zero }
        let scale = min(available.width / imageSize.width, available.height / imageSize.height)
        let size = CGSize(width: imageSize.width * scale, height: imageSize.height * scale)
        return CGRect(
            x: (available.width - size.width) / 2,
            y: (available.height - size.height) / 2,
            width: size.width,
            height: size.height
        )
    }

    private func imagePoint(_ point: CGPoint, rect: CGRect) -> CGPoint? {
        guard rect.contains(point) else { return nil }
        return CGPoint(
            x: (point.x - rect.minX) * imageSize.width / rect.width,
            y: (point.y - rect.minY) * imageSize.height / rect.height
        )
    }

    private func screenPoint(_ point: CGPoint, rect: CGRect) -> CGPoint {
        CGPoint(
            x: rect.minX + point.x * rect.width / imageSize.width,
            y: rect.minY + point.y * rect.height / imageSize.height
        )
    }
}

// MARK: - App entry point

final class EditLockAppDelegate: NSObject, NSApplicationDelegate {
    var stopEngine: (() -> Void)?

    func applicationWillTerminate(_ notification: Notification) {
        stopEngine?()
    }
}

@main
struct EditLockMacApp: App {
    @NSApplicationDelegateAdaptor(EditLockAppDelegate.self) private var appDelegate
    @StateObject private var state = EditLockState()

    var body: some Scene {
        WindowGroup("EditLock") {
            ContentView()
                .environmentObject(state)
                .onAppear { appDelegate.stopEngine = { state.stopEngine() } }
        }
        .defaultSize(width: 1080, height: 760)
    }
}
