import argparse
import code128
import csv
import time

from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont
from pprint import pprint

from secrets import *
from tme import TME
from mouser import Mouser
from digikey import DigiKey
from lcsc import LCSC
from partkeepr import PartKeepr
from distributor_common import SUPPORTED_DISTRIBUTORS, get_part_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=str, required=True, choices=('sync-distributors', 'list-empty-part-mf', 'update-locations-from-csv', 'generate-labels', 'rename-from-params'), help="Which action to perform")
    parser.add_argument("-f", "--force", action='store_true', help="Force certain actions")
    parser.add_argument("-o", "--offset", type=int, required=False, help="Offset into parts list (how many parts to skip)")
    parser.add_argument("--id", type=int, required=False, help="Single part ID")
    parser.add_argument("--location", type=str, required=False, help="Single storage location name")
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
    mouser = Mouser(MOUSER_API_KEY)
    digikey = DigiKey(DIGIKEY_CLIENT_ID, DIGIKEY_CLIENT_SECRET)
    lcsc = LCSC()
    
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
        errors = []
        for i, part in enumerate(parts):
            print("  [{: 5d}/{: 5d}] Processing {}".format(i+1, num_parts, part['name']))
            
            part_distributors = part['distributors']
            part_manufacturers = part['manufacturers']
            part_manufacturer_ids_by_name = dict([(mf['manufacturer']['name'].lower(), mf['@id']) for mf in part_manufacturers])
            
            for distributor in part_distributors:
                distributor_name = distributor['distributor']['name']
                if distributor_name not in SUPPORTED_DISTRIBUTORS.values():
                    print("    Skipping distributor {}".format(distributor_name))
                    continue
                
                print("    Processing distributor {}".format(distributor_name))
                order_no = distributor['orderNumber']
                part_data = get_part_data(distributor_name, order_no, tme, mouser, digikey, lcsc)
                if not part_data:
                    print("      Failed to get part data!")
                    errors.append(part['name'])
                    continue
                part = pk.update_part_data(part, part_data, distributor, manufacturer_ids_by_name)
            time.sleep(0.2) # To ensure we don't exceed 5 API calls per second
        
        if errors:
            print("Parts with errors:")
            print("\n".join(errors))
    
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
            if args.location and loc_name.lower() != args.location.lower():
                continue
            
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
