import requests

BASE = "https://mfp.mpfa.org.hk/mobile/eng"
session = requests.Session()

# Step 1: GET 主页，获取 Session Cookie（JSESSIONID）
session.get(f"{BASE}/mpp_list.jsp", headers={"User-Agent": "Mozilla/5.0"})

# Step 2: 直接 POST 到 download 接口，携带 download() 函数设置的表单字段
payload = {
    "sort_field": "",
    "sort_type": "",
    "showRisk": "CLASS",
    # 若主页还有其它隐藏字段，需一并带上（见下方"完整字段提取"）
}

resp = session.post(
    f"{BASE}/mpp_download_excel.jsp",
    data=payload,
    headers={
        "Referer": f"{BASE}/mpp_list.jsp",
        "Content-Type": "application/x-www-form-urlencoded",
    },
)

# Step 3: 保存 Excel 文件
with open("mpfa_mpp.xlsx", "wb") as f:
    f.write(resp.content)

print("下载完成，文件大小:", len(resp.content), "bytes")
