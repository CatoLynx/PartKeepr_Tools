import base64
import hmac
import requests
import urllib.parse

from hashlib import sha1


class TME:
    def __init__(self, app_key, app_secret):
        self.base_url = "https://api.tme.eu"
        self.app_key = app_key
        self.app_secret = app_secret
    
    def calculate_signature(self, method, url, params):
        sorted_params = sorted(list(params.items()))
        encoded_params_str = urllib.parse.urlencode(sorted_params)
        signature_base = "{}&{}&{}".format(method, urllib.parse.quote_plus(url), urllib.parse.quote_plus(encoded_params_str))
        hashed = hmac.new(self.app_secret.encode('ascii'), signature_base.encode('ascii'), sha1)
        return base64.b64encode(hashed.digest())
    
    def api_call(self, url, params):
        full_url = self.base_url + url
        params['Token'] = self.app_key
        signature = self.calculate_signature("POST", full_url, params)
        params['ApiSignature'] = signature
        resp = requests.post(full_url, data=params)
        if resp.status_code != 200:
            return None
        return resp.json()
    
    def get_part_details(self, order_no):
        data = self.api_call("/Products/GetProducts.json", {"Country": "DE", "Language": "EN", "SymbolList[0]": order_no})
        return data
    
    def get_part_prices(self, order_no):
        data = self.api_call("/Products/GetPrices.json", {"Country": "DE", "Language": "EN", "Currency": "EUR", "SymbolList[0]": order_no})
        return data
    
    def get_part_parameters(self, order_no):
        data = self.api_call("/Products/GetParameters.json", {"Country": "DE", "Language": "EN", "SymbolList[0]": order_no})
        return data
