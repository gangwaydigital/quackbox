import AppKit
import SwiftUI

struct RichEditorOptions: Equatable {
    var fontName: String
    var fontSize: CGFloat
    var textColorHex: String
    var spellCheck: Bool
    var autoDetectLinks: Bool
    var smartQuotes: Bool
    var smartDashes: Bool
}

final class RichTextContext: ObservableObject {
    fileprivate weak var textView: NSTextView?

    fileprivate func attach(_ textView: NSTextView) {
        self.textView = textView
    }

    func toggleBold() {
        applyFontTrait(.boldFontMask)
    }

    func toggleItalic() {
        applyFontTrait(.italicFontMask)
    }

    func toggleUnderline() {
        toggleAttribute(.underlineStyle, onValue: NSUnderlineStyle.single.rawValue)
    }

    func toggleStrikethrough() {
        toggleAttribute(.strikethroughStyle, onValue: NSUnderlineStyle.single.rawValue)
    }

    func insertBulletList() {
        insertPrefixAtCurrentLines("• ")
    }

    func insertNumberedList() {
        guard let textView else { return }
        let selected = textView.selectedRange()
        let nsString = textView.string as NSString
        let lineRange = nsString.lineRange(for: selected)
        let lines = nsString.substring(with: lineRange).components(separatedBy: "\n")
        var number = 1
        let transformed = lines.map { line -> String in
            defer { number += 1 }
            if line.trimmingCharacters(in: .whitespaces).isEmpty { return line }
            return "\(number). \(line)"
        }.joined(separator: "\n")
        textView.textStorage?.replaceCharacters(in: lineRange, with: transformed)
    }

    private func applyFontTrait(_ trait: NSFontTraitMask) {
        guard let textView else { return }
        let manager = NSFontManager.shared
        let range = textView.selectedRange()
        if range.length > 0 {
            textView.textStorage?.beginEditing()
            textView.textStorage?.enumerateAttribute(.font, in: range, options: []) { value, subrange, _ in
                let base = (value as? NSFont) ?? NSFont.systemFont(ofSize: NSFont.systemFontSize)
                let converted = manager.convert(base, toHaveTrait: trait)
                textView.textStorage?.addAttribute(.font, value: converted, range: subrange)
            }
            textView.textStorage?.endEditing()
        } else {
            let current = (textView.typingAttributes[.font] as? NSFont) ?? NSFont.systemFont(ofSize: NSFont.systemFontSize)
            textView.typingAttributes[.font] = manager.convert(current, toHaveTrait: trait)
        }
    }

    private func toggleAttribute(_ key: NSAttributedString.Key, onValue: Any) {
        guard let textView else { return }
        let range = textView.selectedRange()
        if range.length > 0 {
            let existing = textView.textStorage?.attribute(key, at: range.location, effectiveRange: nil)
            let isOn = existing != nil
            if isOn {
                textView.textStorage?.removeAttribute(key, range: range)
            } else {
                textView.textStorage?.addAttribute(key, value: onValue, range: range)
            }
        } else {
            let existing = textView.typingAttributes[key]
            if existing != nil {
                textView.typingAttributes.removeValue(forKey: key)
            } else {
                textView.typingAttributes[key] = onValue
            }
        }
    }

    private func insertPrefixAtCurrentLines(_ prefix: String) {
        guard let textView else { return }
        let selected = textView.selectedRange()
        let nsString = textView.string as NSString
        let lineRange = nsString.lineRange(for: selected)
        let lines = nsString.substring(with: lineRange).components(separatedBy: "\n")
        let transformed = lines.map { line in
            guard !line.trimmingCharacters(in: .whitespaces).isEmpty else { return line }
            return "\(prefix)\(line)"
        }.joined(separator: "\n")
        textView.textStorage?.replaceCharacters(in: lineRange, with: transformed)
    }
}

struct RichTextEditor: NSViewRepresentable {
    @Binding var attributedText: NSAttributedString
    @ObservedObject var context: RichTextContext
    var options: RichEditorOptions

    final class Coordinator: NSObject, NSTextViewDelegate {
        var parent: RichTextEditor
        var isUpdatingFromSwiftUI = false

        init(parent: RichTextEditor) {
            self.parent = parent
        }

        func textDidChange(_ notification: Notification) {
            guard !isUpdatingFromSwiftUI else { return }
            guard let textView = notification.object as? NSTextView else { return }
            parent.attributedText = textView.attributedString()
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.hasHorizontalScroller = false
        scroll.autohidesScrollers = true
        scroll.borderType = .bezelBorder

        let textView = NSTextView()
        textView.isRichText = true
        textView.importsGraphics = true
        textView.usesFontPanel = true
        textView.usesFindBar = true
        textView.allowsUndo = true
        textView.isAutomaticTextCompletionEnabled = true
        textView.isAutomaticQuoteSubstitutionEnabled = options.smartQuotes
        textView.isAutomaticDashSubstitutionEnabled = options.smartDashes
        textView.isAutomaticDataDetectionEnabled = true
        textView.isAutomaticLinkDetectionEnabled = options.autoDetectLinks
        textView.isContinuousSpellCheckingEnabled = options.spellCheck
        textView.isGrammarCheckingEnabled = true
        textView.delegate = context.coordinator
        textView.textStorage?.setAttributedString(attributedText)
        textView.typingAttributes = defaultTypingAttributes(options: options)

        let container = NSTextContainer(size: NSSize(width: 0, height: CGFloat.greatestFiniteMagnitude))
        container.widthTracksTextView = true
        textView.textContainer = container
        textView.minSize = NSSize(width: 0, height: 0)
        textView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false

        scroll.documentView = textView
        self.context.attach(textView)
        return scroll
    }

    func updateNSView(_ nsView: NSScrollView, context: Context) {
        guard let textView = nsView.documentView as? NSTextView else { return }
        self.context.attach(textView)
        textView.isAutomaticQuoteSubstitutionEnabled = options.smartQuotes
        textView.isAutomaticDashSubstitutionEnabled = options.smartDashes
        textView.isAutomaticLinkDetectionEnabled = options.autoDetectLinks
        textView.isContinuousSpellCheckingEnabled = options.spellCheck
        let current = textView.attributedString()
        if !current.isEqual(attributedText) {
            context.coordinator.isUpdatingFromSwiftUI = true
            textView.textStorage?.setAttributedString(attributedText)
            context.coordinator.isUpdatingFromSwiftUI = false
        }
    }

    private func defaultTypingAttributes(options: RichEditorOptions) -> [NSAttributedString.Key: Any] {
        let font = NSFont(name: options.fontName, size: options.fontSize) ?? NSFont.systemFont(ofSize: options.fontSize)
        return [
            .font: font,
            .foregroundColor: NSColor(hex: options.textColorHex) ?? NSColor.labelColor
        ]
    }
}

extension NSAttributedString {
    func toHTMLString() -> String? {
        let range = NSRange(location: 0, length: length)
        let data = try? self.data(
            from: range,
            documentAttributes: [.documentType: NSAttributedString.DocumentType.html]
        )
        guard let data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func fromHTMLString(_ html: String) -> NSAttributedString {
        guard let data = html.data(using: .utf8),
              let value = try? NSAttributedString(
                  data: data,
                  options: [
                      .documentType: NSAttributedString.DocumentType.html,
                      .characterEncoding: String.Encoding.utf8.rawValue
                  ],
                  documentAttributes: nil
              )
        else {
            return NSAttributedString(string: html)
        }
        return value
    }
}

private extension NSColor {
    convenience init?(hex: String) {
        var value = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        if value.hasPrefix("#") { value.removeFirst() }
        guard value.count == 6, let intVal = Int(value, radix: 16) else { return nil }
        let r = CGFloat((intVal >> 16) & 0xFF) / 255.0
        let g = CGFloat((intVal >> 8) & 0xFF) / 255.0
        let b = CGFloat(intVal & 0xFF) / 255.0
        self.init(calibratedRed: r, green: g, blue: b, alpha: 1.0)
    }
}
