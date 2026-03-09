import SwiftUI
import WebKit

struct WebModuleView: NSViewRepresentable {
    let baseURLString: String
    let path: String

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let userContent = WKUserContentController()

        let hideChromeScript = """
        (function() {
          function applyNativeShellMode() {
            try {
              document.querySelectorAll('aside').forEach(function(el) { el.style.display = 'none'; });

              var mobileHeader = document.querySelector('div.md\\:hidden.fixed.top-0.left-0.right-0');
              if (mobileHeader) mobileHeader.style.display = 'none';

              var mobileBottom = document.querySelector('div.md\\:hidden.fixed.bottom-0.left-0.right-0');
              if (mobileBottom) mobileBottom.style.display = 'none';

              document.querySelectorAll('main').forEach(function(main) {
                main.style.paddingTop = '0px';
                main.style.paddingBottom = '0px';
              });

              document.querySelectorAll('.max-w-7xl').forEach(function(container) {
                container.style.maxWidth = 'none';
                container.style.paddingLeft = '16px';
                container.style.paddingRight = '16px';
              });
            } catch (e) {}
          }

          applyNativeShellMode();
          setTimeout(applyNativeShellMode, 50);
          setTimeout(applyNativeShellMode, 250);
          setTimeout(applyNativeShellMode, 1000);
        })();
        """

        let script = WKUserScript(source: hideChromeScript, injectionTime: .atDocumentEnd, forMainFrameOnly: true)
        userContent.addUserScript(script)

        config.userContentController = userContent

        let web = WKWebView(frame: .zero, configuration: config)
        web.allowsBackForwardNavigationGestures = true
        return web
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {
        guard let baseURL = URL(string: baseURLString),
              var comps = URLComponents(url: baseURL, resolvingAgainstBaseURL: false)
        else { return }

        comps.path = path
        guard let url = comps.url else { return }

        if nsView.url != url {
            nsView.load(URLRequest(url: url))
        }
    }
}
