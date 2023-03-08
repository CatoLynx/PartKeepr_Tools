import requests


class LCSC:
    def __init__(self):
        self.base_url = "https://wmsc.lcsc.com"
    
    def get_part_details(self, order_no):
        full_url = self.base_url + "/wmsc/product/detail"
        url_params = {'productCode': order_no}
        cookies = {'currencyCode': "EUR"}
        return requests.get(full_url, params=url_params, cookies=cookies).json()
