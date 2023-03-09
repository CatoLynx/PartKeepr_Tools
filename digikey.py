import json
import requests

from pprint import pprint


class DigiKey:
    def __init__(self, client_id, client_secret):
        self.base_url = "https://api.digikey.com"
        self.auth_data_file = ".dkauth"
        self.auth_data = None
        self.client_id = client_id
        self.client_secret = client_secret
    
    def save_auth_data(self):
        with open(self.auth_data_file, 'w') as f:
                json.dump(self.auth_data, f)
    
    def authorize(self, force_reauth=False):
        reauth = force_reauth
        if not force_reauth:
            try:
                # Get existing token from file
                with open(self.auth_data_file, 'r') as f:
                    self.auth_data = json.load(f)
                return True
            except FileNotFoundError:
                reauth = True
        
        if reauth:
            # Obtain Access Token
            print("Please visit the following URL in your browser to obtain an Authorization Code: https://api.digikey.com/v1/oauth2/authorize?response_type=code&client_id={}&redirect_uri=https%3A%2F%2Fexample.com".format(self.client_id))
            auth_code = input("Please enter the authorization code: ")
            data = {
                'code': auth_code,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': "https://example.com",
                'grant_type': 'authorization_code'
            }
            response = requests.post(self.base_url + "/v1/oauth2/token", data=data).json()
            if 'access_token' in response:
                self.auth_data = {
                    'access_token': response['access_token'],
                    'refresh_token': response['refresh_token']
                }
                self.save_auth_data()
                return True
            return False
        
    def refresh_access_token(self):
        if not self.auth_data:
            return
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.auth_data['refresh_token'],
            'grant_type': 'refresh_token'
        }
        response = requests.post(self.base_url + "/v1/oauth2/token", data=data).json()
        if 'access_token' in response:
            self.auth_data = {
                'access_token': response['access_token'],
                'refresh_token': response['refresh_token']
            }
            self.save_auth_data()
            return True
        else:
            # Failed to refresh, completely re-auth
            return self.authorize(force_reauth=True)
        return False
    
    def api_call(self, url, data=None, retry=True):
        if not self.auth_data:
            success = self.authorize()
            if not success:
                return None
        
        headers = {
            'accept': 'application/json',
            'Authorization': "Bearer {}".format(self.auth_data['access_token']),
            'X-DIGIKEY-Client-Id': self.client_id,
            'X-DIGIKEY-Locale-Site': 'DE',
            'X-DIGIKEY-Locale-Language': 'en',
            'X-DIGIKEY-Locale-Currency': 'EUR',
            'X-DIGIKEY-Customer-Id': "0",
        }
        response = requests.get(self.base_url + url, headers=headers, data=data).json()
        if 'ErrorMessage' in response and response['ErrorMessage'] in ("Bearer token  expired", "The Bearer token is invalid"):
            success = self.refresh_access_token()
            if not success:
                print("Failed to refresh Digi-Key Access Token!")
                return None
            if retry:
                # retry=False to avoid infinite loop on unexpected error
                return self.api_call(url, data, retry=False)
        else:
            return response
    
    def get_part_details(self, order_no):
        return self.api_call("/Search/v3/Products/{}".format(order_no))
