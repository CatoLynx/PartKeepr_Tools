import requests


SUPPORTED_DISTRIBUTORS = {
    "TME": "TME",
    "MSR": "Mouser",
    "DK": "Digi-Key",
    "LCSC": "LCSC"
}


def get_part_data(distributor, order_no, tme, mouser, digikey, lcsc):
    if distributor == "TME":
        tme_data = tme.get_part_details(order_no)
        if tme_data is None:
            print("        TME Part Details API Error!")
            return None
        if 'Error' in tme_data:
            print("        TME Part Details API Error: {}".format(tme_data['Status']))
            return None
        else:
            tme_data = tme_data['Data']['ProductList'][0]
        
        tme_prices = tme.get_part_prices(order_no)
        if tme_prices is None:
            print("        TME Part Prices API Error!")
            return None
        if 'Error' in tme_prices:
            print("        TME Part Prices API Error: {}".format(tme_prices['Status']))
            return None
        else:
            tme_prices = tme_prices['Data']['ProductList'][0]
        
        prices = []
        for entry in tme_prices['PriceList']:
            prices.append({'quantity': entry['Amount'], 'price': entry['PriceValue']})
        
        tme_parameters = tme.get_part_parameters(order_no)
        if tme_parameters is None:
            print("        TME Part Parameters API Error!")
            return None
        if 'Error' in tme_parameters:
            print("        TME Part Parameters API Error: {}".format(tme_parameters['Status']))
            return None
        else:
            tme_parameters = tme_parameters['Data']['ProductList'][0]
        
        parameters = {}
        for entry in tme_parameters['ParameterList']:
            parameters[entry['ParameterName']] = entry['ParameterValue']
        
        part_data = {
            'description': tme_data['Description'],
            'manufacturer': tme_data['Producer'],
            'manufacturer_part_no': tme_data['OriginalSymbol'] or tme_data['Symbol'],
            'photo': tme_data.get('Photo'),
            'parameters': parameters,
            'prices': prices
        }
        if part_data['photo'].startswith("//"):
            part_data['photo'] = "https:" + part_data['photo']
        return part_data
    elif distributor == "Mouser":
        mouser_data = mouser.get_part_details(order_no)
        if mouser_data is None:
            print("        Mouser Part Details API Error!")
            return None
        if mouser_data['Errors']:
            print("        Mouser Part Details API Error!")
            pprint(mouser_data['Errors'])
            return None
        if mouser_data['SearchResults']['NumberOfResult'] == 0:
            print("        Could not find part!")
            return None
        mouser_part = mouser_data['SearchResults']['Parts'][0]
        
        prices = []
        for entry in mouser_part['PriceBreaks']:
            price = float(entry['Price'].split()[0].replace(",", "."))
            prices.append({'quantity': entry['Quantity'], 'price': price})
        
        part_data = {
            'description': mouser_part['Description'],
            'manufacturer': mouser_part['Manufacturer'],
            'manufacturer_part_no': mouser_part['ManufacturerPartNumber'],
            'photo': mouser_part.get('ImagePath'),
            'parameters': None,
            'prices': prices
        }
        return part_data
    elif distributor == "Digi-Key":
        digikey_data = digikey.get_part_details(order_no)
        if digikey_data is None:
            print("        Digi-Key Part Details API Error!")
            return None
        if 'ErrorMessage' in digikey_data:
            print("        Digi-Key Part Details API Error: {}".format(digikey_data['ErrorMessage']))
            return None
        
        prices = []
        for entry in digikey_data['StandardPricing']:
            prices.append({'quantity': entry['BreakQuantity'], 'price': entry['UnitPrice']})
        
        digikey_parameters = digikey_data['Parameters']
        parameters = {}
        for entry in digikey_parameters:
            parameters[entry['Parameter']] = entry['Value']
        
        part_data = {
            'description': digikey_data['ProductDescription'],
            'manufacturer': digikey_data['Manufacturer']['Value'],
            'manufacturer_part_no': digikey_data['ManufacturerPartNumber'],
            'photo': None,
            'parameters': parameters,
            'prices': prices
        }
        
        # For some reason, with Digi-Key, PartKeepr only downloads a "Access Denied" page instead of the photo
        # so we download it ourselves
        if 'PrimaryPhoto' in digikey_data:
            url = digikey_data['PrimaryPhoto']
            filename = url.split("/")[-1]
            with open(filename, 'wb') as f:
                f.write(requests.get(url).content)
            part_data['photo'] = open(filename, 'rb')
        
        return part_data
    elif distributor == "LCSC":
        lcsc_data = lcsc.get_part_details(order_no)
        if lcsc_data is None:
            print("        LCSC Part Details API Error!")
            return None
        if lcsc_data['code'] != 200:
            print("        LCSC Part Details API Error: {}".format(lcsc_data['msg']))
            return None
        if not lcsc_data['result']:
            print("        Could not find part!")
            return None
        lcsc_part = lcsc_data['result']
        
        prices = []
        for entry in lcsc_part['productPriceList']:
            prices.append({'quantity': entry['ladder'], 'price': entry['currencyPrice']})
        
        lcsc_parameters = lcsc_part['paramVOList']
        parameters = {}
        if lcsc_parameters:
            for entry in lcsc_parameters:
                parameters[entry['paramNameEn']] = entry['paramValueEn']
        
        part_data = {
            'description': lcsc_part['productIntroEn'],
            'manufacturer': lcsc_part['brandNameEn'],
            'manufacturer_part_no': lcsc_part['productModel'],
            'photo': lcsc_part['productImages'][0] if lcsc_part['productImages'] else None,
            'parameters': parameters,
            'prices': prices
        }
        return part_data
    return None