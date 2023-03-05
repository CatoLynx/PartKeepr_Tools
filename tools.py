import argparse
import time

from pprint import pprint

from secrets import *
from tme import TME
from partkeepr import PartKeepr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=str, required=True, choices=('sync-distributors', 'list-empty-part-mf'), help="Which action to perform")
    args = parser.parse_args()
    
    pk = PartKeepr(PK_BASE_URL, PK_USERNAME, PK_PASSWORD)
    tme = TME(TME_APP_KEY, TME_APP_SECRET)
    
    if args.action == 'sync-distributors':
        print("Getting parts")
        parts = pk.get_parts()
        print("Getting manufacturers")
        manufacturers = pk.get_manufacturers()
        manufacturer_ids_by_name = dict([(mf['name'].lower(), mf['@id']) for mf in manufacturers])
        
        num_parts = len(parts)
        for i, part in enumerate(parts):
            print("  [{: 5d}/{: 5d}] Processing {}".format(i+1, num_parts, part['name']))
            
            part_distributors = part['distributors']
            part_manufacturers = part['manufacturers']
            part_manufacturer_ids_by_name = dict([(mf['manufacturer']['name'].lower(), mf['@id']) for mf in part_manufacturers])
            
            for distributor in part_distributors:
                print("    Processing distributor {}".format(distributor['distributor']['name']))
                if distributor['distributor']['name'] == "TME":
                    order_no = distributor['orderNumber']
                    print("      Getting info from TME: {}".format(order_no))
                    
                    tme_data = tme.get_part_details(order_no)
                    if 'Error' in tme_data:
                        print("        TME Part Details API Error: {}".format(tme_data['Status']))
                        continue
                    else:
                        tme_data = tme_data['Data']['ProductList'][0]
                        
                    tme_prices = tme.get_part_prices(order_no)
                    if 'Error' in tme_prices:
                        print("        TME Part Prices API Error: {}".format(tme_prices['Status']))
                        continue
                    else:
                        tme_prices = tme_prices['Data']['ProductList'][0]
                    
                    tme_params = tme.get_part_parameters(order_no)
                    if 'Error' in tme_params:
                        print("        TME Part Parameters API Error: {}".format(tme_params['Status']))
                        continue
                    else:
                        tme_params = tme_params['Data']['ProductList'][0]
                    
                    tme_mf = tme_data['Producer']
                    
                    # Update description
                    print("        Updating description")
                    part['description'] = tme_data['Description']
                    result = pk.update_part(part)
                    
                    # Update manufacturer data if available
                    if tme_mf:
                        print("        Manufacturer: {}".format(tme_mf))
                        if tme_mf.lower() in part_manufacturer_ids_by_name:
                            print("        Found part manufacturer entry")
                            part_mf_id = part_manufacturer_ids_by_name[tme_mf.lower()]
                            for mf in part_manufacturers:
                                if mf['@id'] == part_mf_id:
                                    print("        Updating part manufacturer entry")
                                    mf['partNumber'] = tme_data['OriginalSymbol'] or tme_data['Symbol']
                                    result = pk.update_part_manufacturer(mf)
                        else:
                            if tme_mf.lower() in manufacturer_ids_by_name:
                                print("        Found manufacturer in database")
                                mf_id = manufacturer_ids_by_name[tme_mf.lower()]
                            else:
                                print("        Creating manufacturer entry")
                                mf_new = {'name': tme_mf}
                                result = pk.create_manufacturer(mf_new)
                                mf_id = result['@id']
                                manufacturer_ids_by_name[tme_mf.lower()] = mf_id
                            print("        Creating part manufacturer entry")
                            part_mf_new = {'manufacturer': {'@id': mf_id}, 'partNumber': tme_data['OriginalSymbol'] or tme_data['Symbol']}
                            result = pk.create_part_manufacturer(part_mf_new)
                            part_mf_id = result['@id']
                            print("        Linking part manufacturer to part")
                            part['manufacturers'].append({'@id': part_mf_id})
                            result = pk.update_part(part)
                    else:
                        print("        No manufacturer found!")
                    
                    # Update pricing data
                    if len(tme_prices['PriceList']) >= 1:
                        new_price = tme_prices['PriceList'][0]['PriceValue'] # Always use lowest quantity group
                        print("        Updating price from {} to {:.5f}".format(distributor['price'], new_price))
                        distributor['price'] = new_price
                        result = pk.update_part_distributor(distributor)
                    
                    # Update image if no image attachment is present and TME has a photo
                    if not [a['isImage'] for a in part['attachments']] and tme_data.get('Photo'):
                        print("        Updating photo")
                        photo_url = tme_data['Photo']
                        if photo_url.startswith("//"):
                            photo_url = "https:" + photo_url
                        result = pk.upload_temp_file_from_url(photo_url)
                        file_id = result['image']['@id']
                        part['attachments'].append({'@id': file_id})
                        result = pk.update_part(part)
                    
                    # Update parameters
                    # For now, all parameters are treated as text and the PartKeepr Unit system is not used.
                    if len(tme_params['ParameterList']) >= 1:
                        print("        Updating parameters")
                        for param in tme_params['ParameterList']:
                            param_name = param['ParameterName']
                            param_value = param['ParameterValue']
                            param_found = False
                            for j, existing_param in enumerate(part['parameters']):
                                if existing_param['name'] == param_name:
                                    part['parameters'][j]['stringValue'] = param_value
                                    param_found = True
                                    break
                            if not param_found:
                                part['parameters'].append({'name': param_name, 'stringValue': param_value})
                        result = pk.update_part(part)
            time.sleep(0.2) # To ensure we don't exceed 5 TME API calls per second
    elif args.action == 'list-empty-part-mf':
        print("Getting parts")
        parts = pk.get_parts()
        num_parts = len(parts)
        
        empty_mf_parts = []
        for i, part in enumerate(parts):
            print("  [{: 5d}/{: 5d}] Processing {}".format(i+1, num_parts, part['name']))
            part_manufacturers = part['manufacturers']
            if not part_manufacturers:
                empty_mf_parts.append(part['name'])
        
        print("Parts without part manufacturers:")
        print("\n".join(empty_mf_parts))
            

if __name__ == "__main__":
    main()
