import requests


class Mouser:
    def __init__(self, api_key):
        self.base_url = "https://api.mouser.com"
        self.api_key = api_key
    
    def get_part_details(self, order_no):
        full_url = self.base_url + "/api/v2/search/partnumber"
        url_params = {'apiKey': self.api_key}
        json = {
            'SearchByPartRequest': {
                'mouserPartNumber': order_no,
                'partSearchOptions': None
            }
        }
        return requests.post(full_url, params=url_params, json=json).json()
