import AppKit
import SwiftUI
import UniformTypeIdentifiers

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
