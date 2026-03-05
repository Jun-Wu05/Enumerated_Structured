# Page 2

技术文档 技术文档 2
HTTP API 文档 2
Syslog 文档 13
基线标准文档 37
技术架构 90
入侵场景复现 90
其他技术文档 102
01  / 111

---

# Page 3

技术文档 技术文档
HTTP API 文档 文档
API Token
使用方式 使用方式
API 说明
所有 HTTP API 均使用 JSONRPC 调用方式，其中：
请求 请求 URL：  https://{管理平台 IP 地址}/rpc 
请求方式 请求方式：  POST 
Content-Type：  application/json;charset=UTF-8 
Body： JSON 格式，其中包含 4 个字段
id： 必选，字符串，例  63845f41-b556-995a-c6e5 
jsonrpc： 必选，字符串，永远是  "2.0" 
method： 请求方法，必选，字符串，参考不同功能的 API 文档
params： 请求参数，可选，字典，参考不同功能的 API 文档
Python3 示范调用
封装一个简单的 API 类
将以下代码保存为  API.py  文件
注意，以下代码需要依赖第三方库  requests  ,  cryptography 
import requests
import json
from urllib.parse import urljoin
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
class API(object):
    def __init__(self, url):
        self.url = urljoin(url, "/rpc")
        self.cookies = {}
    
def login_with_token(self, token):
        self.cookies["API-Token"] = token
    def get_public_key(self):
        resp = self.request("CloudwalkerSettingService.GetPublicKey", {}, raw_response=True)
        resp.raise_for_status()
02  / 111

---

# Page 4

resp.raise_for_status()
        response_json = resp.json()
        public_key_base64 = response_json.get(
'result', {}).get('public_key')
        if not public_key_base64:
            raise ValueError("Public key not found in the API response.")
        return base64.b64decode(public_key_base64)
    def encrypt_password(self, passwd, public_key_pem):
        public_key = serialization.load_pem_public_key(public_key_pem)
        encrypted_passwd = public_key.encrypt(
            passwd,
            padding.PKCS1v15()
        )
        
return base64.b64encode(encrypted_passwd).decode('utf-8')
    def login_with_password(self, username, password):
        # 获取公钥
        public_key_pem = self.get_public_key()
        
# 加密密码
        encrypted_password = self.encrypt_password(password.encode('utf-8'), public_key_pem)
        # 发送带有加密后密码的登录请求
        resp = self.request("AccountNoAuthService.Login", 
                            {"username": username, "type": "", "credentials": {"password": encrypted_password}}, 
                            True)
        if resp.status_code == 200 and "error" not in resp.json():
            self.cookies["sessionid"] = resp.cookies.get("sessionid", None)
    def request(self, method, params, raw_response=False):
        data = {
            
"method": method,
            "params": params,
            "jsonrpc": "2.0",
            "id": "0"  # 使用固定的ID或生成一个随机的ID
        }
        headers = {
            
'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        }
        resp = requests.post(self.url, headers=headers, data=json.dumps(data), cookies=self.cookies, verify=
False)
        if raw_response:
            return resp
        else:
            return resp.json()
这段代码包含一个 API 类，提供了 6 个外部接口：
03  / 111

---

# Page 5

1. 构造函数 构造函数: 包含 1 个参数，填入管理界面的地址即可
2. login_with_token: 包含 1 个参数，填入在管理界面上生成的 API Token 即可
3. get_public_key: 不用传参数，获取服务端的public_key 用来加密用户密码
4. encrypt_password：包含 2 个参数，分别是加密的公钥名和密码
5. login_with_password: 包含 2 个参数，分别是用户名和密码
6. request: 包含 2 个参数，分别为请求方法 (method) 和请求参数 (params)，详见具体的 API 文档
使用 Token 登录，并使用 API 获取告警配置
from API import API
api = API("https://{server_address}/")
api.login_with_token("************")
result = api.request(
        
"AlertConfigService.List",
        {
            
"count": 20,
            "offset": 0
        }
    )
print(result)
使用密码登录，并使用 API 获取告警配置
from API import API
api = API("https://{server_address}/")
api.login_with_password("username", "password")
result = api.request(
        
"AlertConfigService.List",
        {
            
"count": 20,
            "offset": 0
        }
    )
print(result)
入侵检测 入侵检测
入侵检测统计
拉取最新的入侵事件
请求 请求
04  / 111