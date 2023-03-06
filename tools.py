import argparse
import code128
import csv
import time

from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont
from pprint import pprint

from secrets import *
from tme import TME
from partkeepr import PartKeepr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=str, required=True, choices=('sync-distributors', 'list-empty-part-mf', 'update-locations-from-csv', 'generate-labels', 'rename-from-params'), help="Which action to perform")
    parser.add_argument("-f", "--force", action='store_true', help="Force certain actions")
    parser.add_argument("-o", "--offset", type=int, required=False, help="Offset into parts list (how many parts to skip)")
    parser.add_argument("--id", type=int, required=False, help="Single part ID")
    parser.add_argument("--name-column", type=str, required=False, help="For CSV import: Name column name")
    parser.add_argument("--location-column", type=str, required=False, help="For CSV import: Storage location column name")
    parser.add_argument("--default-location", type=str, required=False, help="For CSV import: Default storage location if none is found")
    parser.add_argument("--csv-file", type=str, required=False, help="For CSV import: CSV file name")
    parser.add_argument("--label-width", type=int, required=False, help="For label generation: Label width in millimeters")
    parser.add_argument("--label-height", type=int, required=False, help="For label generation: Label height in millimeters")
    parser.add_argument("--label-dpi", type=int, required=False, help="For label generation: Label resolution in dpi")
    parser.add_argument("--font-size", type=int, required=False, help="For label generation: Font size")
    parser.add_argument("--max-parts-per-label", type=int, required=False, help="For label generation: Only generate label for maximum of n parts")
    parser.add_argument("--label-file", type=str, required=False, help="For label generation: Label PDF file name")
    args = parser.parse_args()
    
    pk = PartKeepr(PK_BASE_URL, PK_USERNAME, PK_PASSWORD)
    tme = TME(TME_APP_KEY, TME_APP_SECRET)
    
    if args.action == 'sync-distributors':
        if args.id:
            print("Getting part")
            parts = [pk.get_part(args.id)]
        else:
            print("Getting parts")
            parts = pk.get_parts()
        
        print("Getting manufacturers")
        manufacturers = pk.get_manufacturers()
        manufacturer_ids_by_name = dict([(mf['name'].lower(), mf['@id']) for mf in manufacturers])
        
        if args.offset:
            parts = parts[args.offset:]
        
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
    
    elif args.action == 'update-locations-from-csv':
        if not args.name_column or not args.location_column or not args.csv_file or not args.default_location:
            print("Error: Missing parameters!")
            return
        
        if args.id:
            print("Getting part")
            parts = [pk.get_part(args.id)]
        else:
            print("Getting parts")
            parts = pk.get_parts()
        
        part_indices_by_name = dict([(part['name'].lower(), index) for index, part in enumerate(parts)])
        
        print("Getting storage locations")
        locations = pk.get_storage_locations()
        location_ids_by_name = dict([(loc['name'].lower(), loc['@id']) for loc in locations])
        
        entries = []
        with open(args.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=',', quotechar='"')
            for row in reader:
                entries.append(row)
        
        for entry in entries:
            name = entry[args.name_column]
            location = entry[args.location_column]
            if not location:
                location = args.default_location
            print("Processing {} located in {}".format(name, location))
            
            if name.lower() not in part_indices_by_name:
                print("  Could not find part in database, skipping")
                continue
            
            part_index = part_indices_by_name[name.lower()]
            part = parts[part_index]
            if part['storageLocation'] and not args.force:
                print("  Part already has storage location assigned, skipping (use -f to override)")
                continue
            
            if location.lower() in location_ids_by_name:
                print("  Found location in database")
                loc_id = location_ids_by_name[location.lower()]
            else:
                print("  Creating location")
                loc_new = {'name': location, 'category': {'@id': "/api/storage_location_categories/1"}}
                result = pk.create_storage_location(loc_new)
                loc_id = result['@id']
                location_ids_by_name[location.lower()] = loc_id
            
            print("  Updating part")
            part['storageLocation'] = {'@id': loc_id}
            result = pk.update_part(part)
    
    elif args.action == 'generate-labels':
        if not args.label_width or not args.label_height or not args.label_dpi or not args.font_size or not args.max_parts_per_label or not args.label_file:
            print("Error: Missing parameters!")
            return
        
        label_width_px = round((args.label_width / 25.4) * args.label_dpi)
        label_height_px = round((args.label_height / 25.4) * args.label_dpi)
        
        print("Getting parts")
        parts = pk.get_parts()
        parts_by_location = {}
        
        for part in parts:
            if not part['storageLocation']:
                continue
            loc_name = part['storageLocation']['name']
            if loc_name in parts_by_location:
                parts_by_location[loc_name].append(part)
            else:
                parts_by_location[loc_name] = [part]
        
        labels = []
        font = ImageFont.truetype("LiberationSans-Regular.ttf", args.font_size)
        for loc_name, parts in sorted(parts_by_location.items(), key=lambda e: e[0]):
            if len(parts) > args.max_parts_per_label:
                print("Skipping storage location {}: {} parts".format(loc_name, len(parts)))
                continue
            print("Processing storage location {}: {} parts".format(loc_name, len(parts)))
            
            img = Image.new("RGB", (label_width_px, label_height_px), 'white')
            draw = ImageDraw.Draw(img)
            
            margin = round(max(label_height_px * 0.02, label_width_px * 0.02))
            avail_label_height = label_height_px - 2 * margin
            avail_label_width = label_width_px - 2 * margin
            
            # Split label into base grid with fixed height location tag and variable height parts areas
            base_x = margin
            loc_area_y = margin
            loc_area_height = round(args.font_size * 1.5)
            parts_area_y = loc_area_y + loc_area_height
            parts_area_height = avail_label_height - loc_area_height
            
            # Split parts area into evenly-spaced grid
            parts_area_region_height = parts_area_height // len(parts)
            parts_area_regions_y = []
            for i in range(len(parts)):
                region_y = parts_area_y + parts_area_region_height * i
                parts_area_regions_y.append(region_y)
            
            draw.text((base_x, loc_area_y), "Location: {}".format(loc_name), 'black', font=font)
            
            for i, part in enumerate(sorted(parts, key=lambda p: p['@id'])):
                barcode_text = "{}: {}".format(part['category']['name'], part['name'])
                
                part_id = part['@id'].split("/")[-1]
                barcode_height = parts_area_region_height - round(args.font_size * 1.5)
                barcode_thickness = avail_label_width // 100
                
                barcode = code128.image("P" + part_id, height=barcode_height, thickness=barcode_thickness, quiet_zone=False)
                barcode_x = (avail_label_width - (barcode.size[0])) // 2
                barcode_y = parts_area_regions_y[i]
                img.paste(barcode, (barcode_x, barcode_y))
                
                name_x = barcode_x
                name_y = barcode_y + barcode_height + args.font_size * 0.1
                draw.text((name_x, name_y), barcode_text, 'black', font=font)
            
            labels.append(img)
        
        print("Generating PDF")
        labels[0].save(args.label_file, "PDF", resolution=args.label_dpi, save_all=True, append_images=labels[1:])
    
    elif args.action == 'rename-from-params':
        if args.id:
            print("Getting part")
            parts = [pk.get_part(args.id)]
        else:
            print("Getting parts")
            parts = pk.get_parts()
        
        num_parts = len(parts)
        for i, part in enumerate(parts):
            print("  [{: 5d}/{: 5d}] Processing {}".format(i+1, num_parts, part['name']))
            
            new_name = ""
            param_dict = defaultdict(lambda: "", [(p['name'], p['stringValue']) for p in part['parameters']])
            
            # The following code needs to be customized depensing on your organization.
            # It handles generating short part descriptions to print
            # instead of the part number for certain kinds of parts, like resistors.
            category = part['category']['name']
            if category in ["Resistors"]:
                new_name = "{Number of resistors} {Resistance} {Tolerance} {Power} {Case - inch} {Mounting}".format_map(param_dict)
            elif category in ["Ceramic Caps"]:
                new_name = "{Capacitance} {Tolerance} {Operating voltage} {Dielectric} {Case - inch} {Mounting}".format_map(param_dict)
            elif category in ["Electrolytic Caps"]:
                new_name = "{Capacitance} {Tolerance} {Operating voltage} {Mounting}".format_map(param_dict)
            elif category in ["Tantalum Caps"]:
                new_name = "{Capacitance} {Tolerance} {Operating voltage} {Case} {Mounting}".format_map(param_dict)
            elif category in ["Fuses"]:
                new_name = "{Current rating} {Fuse characteristics} {Rated voltage} {Mounting}".format_map(param_dict)
            new_name = " ".join(new_name.split())
            
            if not new_name.strip():
                print("    Renaming would result in empty name, skipping")
                continue
            
            if new_name == part['name']:
                print("    Name unchanged, skipping")
                continue
            
            accept = input("    Rename {} to {}? [Y/n] ".format(part['name'], new_name)).lower() in ("", "y")
            if accept:
                print("    Updating part")
                part['name'] = new_name
                result = pk.update_part(part)

if __name__ == "__main__":
    main()
