import io
import json
import os
import requests


class PartKeepr:
    def __init__(self, base_url, username, password):
        # base_url is something like https://my.partkeepr.host (no trailing slash)
        self.base_url = base_url
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.user = self.login()
    
    def login(self):
        return self.session.post(self.base_url + "/api/users/login").json()
    
    def get(self, url, params=None):
        return self.session.get(self.base_url + url, params=params).json()
    
    def create(self, url, data, params=None):
        return self.session.post(self.base_url + url, json=data, params=params).json()
    
    def update(self, url, data, params=None):
        return self.session.put(self.base_url + url, json=data, params=params).json()
    
    def delete(self, url, params=None):
        self.session.delete(self.base_url + url, params=params)
    
    def upload(self, url, file, params=None):
        return self.session.post(self.base_url + url, files=file, params=params).json()
    
    def get_paged(self, url, params=None):
        result = []
        next_page = url
        while next_page:
            data = self.get(next_page, params=params)
            result.extend(data['hydra:member'])
            next_page = data.get('hydra:nextPage')
        return result
    
    def get_parts(self, filter=None):
        if filter:
            params = {'filter': json.dumps([filter])}
        else:
            params = None
        return self.get_paged("/api/parts", params=params)
    
    def get_part(self, part_id):
        return self.get("/api/parts/{}".format(part_id))
    
    def get_manufacturers(self):
        return self.get_paged("/api/manufacturers")
    
    def get_distributors(self):
        return self.get_paged("/api/distributors")
    
    def get_storage_locations(self):
        return self.get_paged("/api/storage_locations")
    
    def get_project(self, project_id):
        return self.get("/api/projects/{}".format(project_id))
    
    def create_part(self, part):
        return self.create("/api/parts", part)
    
    def create_manufacturer(self, manufacturer):
        return self.create("/api/manufacturers", manufacturer)
    
    def create_part_manufacturer(self, part_manufacturer):
        return self.create("/api/part_manufacturers", part_manufacturer)
    
    def create_part_distributor(self, part_distributor):
        return self.create("/api/part_distributors", part_distributor)
    
    def create_storage_location(self, storage_location):
        return self.create("/api/storage_locations", storage_location)
    
    def create_project_part(self, project_part):
        return self.create("/api/project_parts", project_part)
    
    def update_part(self, part):
        return self.update(part['@id'], part)
    
    def update_part_manufacturer(self, part_manufacturer):
        return self.update(part_manufacturer['@id'], part_manufacturer)
    
    def update_part_distributor(self, part_distributor):
        return self.update(part_distributor['@id'], part_distributor)
    
    def update_project(self, project):
        return self.update(project['@id'], project)
    
    def upload_temp_file(self, file):
        return self.upload("/api/temp_uploaded_files/upload", {'userfile': file})
    
    def upload_temp_file_from_url(self, url):
        return self.create("/api/temp_uploaded_files/upload", {'url': url})
    
    def part_add_stock(self, part_id, quantity):
        return self.update(part_id + "/addStock", {'quantity': quantity})
    
    def part_remove_stock(self, part_id, quantity):
        return self.update(part_id + "/removeStock", {'quantity': quantity})
    
    def part_set_stock(self, part_id, quantity):
        return self.update(part_id + "/setStock", {'quantity': quantity})
    
    def update_part_data(self, part, part_data, distributor, manufacturer_ids_by_name=None):
        if not manufacturer_ids_by_name:
            print("Getting manufacturers")
            manufacturers = self.get_manufacturers()
            manufacturer_ids_by_name = dict([(mf['name'].lower(), mf['@id']) for mf in manufacturers])
        
        part_manufacturers = part['manufacturers']
        part_manufacturer_ids_by_name = dict([(mf['manufacturer']['name'].lower(), mf['@id']) for mf in part_manufacturers]) 
        
        # Update description
        if part_data['description']:
            print("        Updating description")
            part['description'] = part_data['description']
        
        # Update manufacturer data if available
        if part_data['manufacturer']:
            print("        Manufacturer: {}".format(part_data['manufacturer']))
            if part_data['manufacturer'].lower() in part_manufacturer_ids_by_name:
                print("        Found part manufacturer entry")
                part_mf_id = part_manufacturer_ids_by_name[part_data['manufacturer'].lower()]
                for mf in part_manufacturers:
                    if mf['@id'] == part_mf_id:
                        print("        Updating part manufacturer entry")
                        mf['partNumber'] = part_data['manufacturer_part_no']
                        result = self.update_part_manufacturer(mf)
            else:
                if part_data['manufacturer'].lower() in manufacturer_ids_by_name:
                    print("        Found manufacturer in database")
                    mf_id = manufacturer_ids_by_name[part_data['manufacturer'].lower()]
                else:
                    print("        Creating manufacturer entry")
                    mf_new = {'name': part_data['manufacturer']}
                    result = self.create_manufacturer(mf_new)
                    mf_id = result['@id']
                    manufacturer_ids_by_name[part_data['manufacturer'].lower()] = mf_id
                print("        Creating part manufacturer entry")
                part_mf_new = {'manufacturer': {'@id': mf_id}, 'partNumber': part_data['manufacturer_part_no']}
                result = self.create_part_manufacturer(part_mf_new)
                part_mf_id = result['@id']
                print("        Linking part manufacturer to part")
                part['manufacturers'].append({'@id': part_mf_id})
        else:
            print("        No manufacturer found!")
        
        # Update pricing data
        if part_data['prices']:
            new_price = part_data['prices'][0]['price'] # Always use lowest quantity group
            print("        Updating price from {} to {:.5f}".format(distributor['price'], new_price))
            distributor['price'] = new_price
            result = self.update_part_distributor(distributor)
        
        # Update image if no image attachment is present and distributor has a photo
        if not [a['isImage'] for a in part['attachments']] and part_data['photo']:
            print("        Updating photo")
            if isinstance(part_data['photo'], io.IOBase):
                result = self.upload_temp_file(part_data['photo'])
                part_data['photo'].close()
                os.remove(part_data['photo'].name)
            else:
                result = self.upload_temp_file_from_url(part_data['photo'])
            file_id = result['image']['@id']
            part['attachments'].append({'@id': file_id})
        
        # Update parameters
        # For now, all parameters are treated as text and the PartKeepr Unit system is not used.
        if part_data['parameters']:
            print("        Updating parameters")
            for param_name, param_value in part_data['parameters'].items():
                param_found = False
                for j, existing_param in enumerate(part['parameters']):
                    if existing_param['name'] == param_name:
                        part['parameters'][j]['stringValue'] = param_value
                        param_found = True
                        break
                if not param_found:
                    part['parameters'].append({'name': param_name, 'stringValue': param_value})
        
        # Update part in database
        return self.update_part(part)
