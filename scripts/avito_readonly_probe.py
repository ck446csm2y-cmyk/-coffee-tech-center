#!/usr/bin/env python3
"""Read-only Avito API probe for Autoload access."""
import json, os, sys, urllib.error, urllib.parse, urllib.request
TOKEN_URL="https://api.avito.ru/token/"; API_BASE="https://api.avito.ru"

def req(url, token):
    r=urllib.request.Request(url,method="GET",headers={"Accept":"application/json","Authorization":f"Bearer {token}","User-Agent":"coffee-tech-center-avito-probe/2.4"})
    try:
        with urllib.request.urlopen(r,timeout=25) as x:
            raw=x.read().decode(); return x.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors="replace")
        try: body=json.loads(raw) if raw else None
        except: body={"raw":raw[:500]}
        return e.code, body

def main():
    cid=os.environ.get("AVITO_CLIENT_ID","").strip(); sec=os.environ.get("AVITO_CLIENT_SECRET","").strip()
    if not cid or not sec: raise SystemExit("missing secrets")
    data=urllib.parse.urlencode({"grant_type":"client_credentials","client_id":cid,"client_secret":sec}).encode()
    r=urllib.request.Request(TOKEN_URL,data=data,method="POST",headers={"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(r,timeout=20) as x: token=json.loads(x.read().decode())["access_token"]
    print("AVITO_AUTH_OK=true")
    for path,label in [("/autoload/v1/profile","AUTOLOAD_V1_PROFILE"),("/autoload/v2/profile","AUTOLOAD_V2_PROFILE"),("/autoload/v2/reports?per_page=1&page=1","AUTOLOAD_REPORTS")]:
        status,body=req(API_BASE+path,token)
        print(f"{label}_HTTP={status}")
        if status==200:
            safe=body
            if label.startswith("AUTOLOAD_V1") and isinstance(body,dict):
                safe={"autoload_enabled":body.get("autoload_enabled"),"has_upload_url":bool(body.get("upload_url")),"schedule_present":bool(body.get("schedule"))}
            if label.startswith("AUTOLOAD_V2") and isinstance(body,dict):
                safe={"autoload_enabled":body.get("autoload_enabled"),"feeds_count":len(body.get("feeds_data") or []) if isinstance(body.get("feeds_data"),list) else None,"schedule_present":bool(body.get("schedule"))}
            print(label+"_SAFE="+json.dumps(safe,ensure_ascii=False)[:3000])
    print("READ_ONLY_CHECK_COMPLETE=true")
if __name__=="__main__": main()
