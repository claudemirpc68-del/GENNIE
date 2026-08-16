import httpx

clients = [
    "718713040806-bvfmni907pda73diko9smt2r0psianbo.apps.googleusercontent.com",
    "718713040806-cv97ii7lm85cffj6a400k1m5a4v3j460.apps.googleusercontent.com",
    "718713040806-pc3n649glc2u8bfospmuvn0nibp30mnu.apps.googleusercontent.com",
    "718713040806-q0qaesuholcjm7cab12sk5vgoma8ngrv.apps.googleusercontent.com",
    "718713040806-uemi9h9bi1qeqns8qlk461ipou84kqvs.apps.googleusercontent.com",
    "187149655163-b0qujv3vcmhfg1ja4h8ei7ue43inapdp.apps.googleusercontent.com",
    "187149655163-d1q3hon8gr2asuauh0rknsce6143otr8.apps.googleusercontent.com",
    "187149655163-mm8fb51rd8m60cj3pb3g7upvkfure7hk.apps.googleusercontent.com",
    "1062142725046-ttvtovbdmlj0rdv2cshjfejq6593s8ce.apps.googleusercontent.com",
    "1062142725046-v3tkfotsve003ho7cjo71uvt3dcuv98h.apps.googleusercontent.com",
]

for cid in clients:
    uri = (
        f"https://accounts.google.com/o/oauth2/v2/auth?client_id={cid}"
        f"&redirect_uri=http://localhost&response_type=code"
        f"&scope=email%20https://www.googleapis.com/auth/gmail.readonly&prompt=select_account"
    )
    try:
        r = httpx.get(uri, follow_redirects=False, timeout=20)
        body = r.text
        if "deleted_client" in body:
            print(f"{cid[:32]}... => DELETADO")
        elif r.status_code in (302, 303, 200):
            loc = r.headers.get("location", "")
            print(f"{cid[:32]}... => ATIVO (HTTP {r.status_code} loc={loc[:70]})")
        else:
            print(f"{cid[:32]}... => HTTP {r.status_code}")
    except Exception as e:
        print(f"{cid[:32]}... => ERRO {type(e).__name__}: {str(e)[:70]}")
