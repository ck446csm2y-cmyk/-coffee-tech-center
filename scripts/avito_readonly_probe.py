#!/usr/bin/env python3
"""Read-only Avito API probe for account/items and Autoload access."""
import json, os, urllib.error, urllib.parse, urllib.request
TOKEN_URL="https://api.avito.ru/token/"; API_BASE="https://api.avito.ru"

def req(url, token):
    r=urllib.request.Request(url,method="GET",headers={"Accept":"application/json","Authorization":f"Bearer {token}","User-Agent":"coffee-tech-center-avito-probe/2.5"})
    try:
        with urllib.request.urlopen(r,timeout=25) as x:
            raw=x.read().decode(); return x.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors="replace")
        try: body=json.loads(raw) if raw else None
        except: body={"raw":raw[:500]}
        return e.code, body

def safe_items(body):
    if not isinstance(body,dict): return body
    resources=body.get("resources") or body.get("items") or []
    out=[]
    for it in resources[:20]:
        if not isinstance(it,dict): continue
        out.append({k:it.get(k) for k in ("id","title","status","category","price","address","url") if k in it})
    return {"count":len(resources),"items":out}

def main():
    cid=os.environ.get("AVITO_CLIENT_ID","").strip(); sec=os.environ.get("AVITO_CLIENT_SECRET","").strip()
    if not cid or not sec: raise SystemExit("missing secrets")
    data=urllib.parse.urlencode({"grant_type":"client_credentials","client_id":cid,"client_secret":sec}).encode()
    r=urllib.request.Request(TOKEN_URL,data=data,method="POST",headers={"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(r,timeout=20) as x: token=json.loads(x.read().decode())["access_token"]
    print("AVITO_AUTH_OK=true")
    for path,label in [
        ("/core/v1/accounts/self","ACCOUNT_SELF"),
        ("/core/v1/items?status=active&limit=100&offset=0","ACTIVE_ITEMS"),
        ("/autoload/v1/profile","AUTOLOAD_V1_PROFILE"),
        ("/autoload/v2/profile","AUTOLOAD_V2_PROFILE")]:
        status,body=req(API_BASE+path,token); print(f"{label}_HTTP={status}")
        if status==200:
            if label=="ACCOUNT_SELF" and isinstance(body,dict):
                safe={k:body.get(k) for k in ("id","name","email","phone") if k in body}
            elif label=="ACTIVE_ITEMS": safe=safe_items(body)
            elif label.startswith("AUTOLOAD_V1") and isinstance(body,dict): safe={"autoload_enabled":body.get("autoload_enabled"),"has_upload_url":bool(body.get("upload_url")),"schedule_present":bool(body.get("schedule"))}
            elif label.startswith("AUTOLOAD_V2") and isinstance(body,dict): safe={"autoload_enabled":body.get("autoload_enabled"),"feeds_count":len(body.get("feeds_data") or []) if isinstance(body.get("feeds_data"),list) else None,"schedule_present":bool(body.get("schedule"))}
            else: safe=body
            print(label+"_SAFE="+json.dumps(safe,ensure_ascii=False)[:12000])
    print("READ_ONLY_CHECK_COMPLETE=true")
if __name__=="__main__": main()
